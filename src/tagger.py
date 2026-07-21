"""
PRM tagger — Lambda-backed CloudFormation custom resource.

Applies the AWS Partner Revenue Measurement tag (aws-apn-id = pc:<product-code>)
to existing resources in the account/region, using the Resource Groups Tagging API.

This is the readable, canonical copy of the handler. A byte-compact version of the
same logic is embedded inline in each CloudFormation template (templates/*.yaml) so
the templates are self-contained and need no S3 packaging.

Behaviour
---------
- Rules are evaluated in order. Each resource is tagged with the FIRST matching
  rule's product code — AWS resources can carry only one aws-apn-id tag, so order
  = priority.
- A rule matches by resourceTypes (Resource Groups Tagging API ResourceTypeFilters)
  and/or tagFilters (TagFilters). A rule with neither matches every taggable
  resource in the region.
- PRESERVE (default true): resources that ALREADY carry an aws-apn-id tag with a
  DIFFERENT value (i.e. another partner's tag) are left untouched. Set PRESERVE=false
  to overwrite. Resources already carrying the intended value are skipped as no-ops.
- Cost Explorer is the other PRM prerequisite. The handler checks whether Cost
  Explorer is enabled (a ce:GetCostAndUsage probe) and reports the result to
  CloudFormation outputs and to the optional phone-home beacon. It cannot enable
  Cost Explorer (AWS has no such API — it is enabled from the Billing console).
- PHONE_HOME_URL (optional): after tagging, the handler POSTs a small JSON beacon
  {event, account, region, tagged, ceEnabled, codes} to this URL so the partner can
  track deployment/compliance centrally.
- On a scheduled EventBridge invoke (event has no "RequestType") it re-applies the
  same rules — catching resources created since the last run — and beacons.
- On CloudFormation Delete it does nothing unless RemoveOnDelete is "true", in which
  case it removes the aws-apn-id tag from every resource that carries it.

Per-resource tagging failures (e.g. Kubernetes pods, deleted snapshots) are returned
by the API in FailedResourcesMap and are intentionally ignored — they never fail the
stack.
"""
import datetime
import json
import os
import urllib.request

import boto3

TAG_KEY = "aws-apn-id"


def _get_mappings(client, **filters):
    """Return all resource-tag mappings (ARN + Tags) matching the filters."""
    out, token = [], None
    while True:
        if token:
            filters["PaginationToken"] = token
        resp = client.get_resources(ResourcesPerPage=100, **filters)
        out += resp["ResourceTagMappingList"]
        token = resp.get("PaginationToken")
        if not token:
            break
    return out


def _in_batches(arns, fn, size=20):
    for i in range(0, len(arns), size):
        fn(arns[i:i + size])


def _existing_apn_id(mapping):
    for tag in mapping.get("Tags", []):
        if tag["Key"] == TAG_KEY:
            return tag["Value"]
    return None


def apply_rules(client, rules, preserve_existing):
    """Tag resources per the ordered rule list. Returns count tagged.

    preserve_existing=True skips resources already carrying a different partner's
    aws-apn-id value, so we never clobber another partner's attribution.
    """
    assigned, total = set(), 0
    for rule in rules:
        filters = {}
        if rule.get("resourceTypes"):
            filters["ResourceTypeFilters"] = rule["resourceTypes"]
        if rule.get("tagFilters"):
            filters["TagFilters"] = rule["tagFilters"]
        value = "pc:" + rule["productCode"]
        arns = []
        for mapping in _get_mappings(client, **filters):
            arn = mapping["ResourceARN"]
            if arn in assigned:
                continue
            existing = _existing_apn_id(mapping)
            if existing == value:      # already correct — no-op
                assigned.add(arn)
                continue
            if existing and preserve_existing:  # another partner's tag — keep it
                continue
            arns.append(arn)
        _in_batches(
            arns,
            lambda batch, v=value: client.tag_resources(
                ResourceARNList=batch, Tags={TAG_KEY: v}
            ),
        )
        assigned.update(arns)
        total += len(arns)
    return total


def remove_all(client):
    arns = [m["ResourceARN"]
            for m in _get_mappings(client, TagFilters=[{"Key": TAG_KEY}])]
    _in_batches(
        arns,
        lambda batch: client.untag_resources(
            ResourceARNList=batch, TagKeys=[TAG_KEY]
        ),
    )
    return len(arns)


def cost_explorer_enabled():
    """PRM prerequisite check. True if Cost Explorer answers a query."""
    try:
        end = datetime.date.today()
        start = end - datetime.timedelta(days=1)
        boto3.client("ce").get_cost_and_usage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Granularity="DAILY", Metrics=["UnblendedCost"],
        )
        return True
    except Exception:  # noqa: BLE001 — any failure means "not usable"
        return False


def phone_home(url, payload):
    """Best-effort telemetry beacon; never raises."""
    if not url:
        return
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:  # noqa: BLE001
        pass


def handler(event, context):
    client = boto3.client("resourcegroupstaggingapi")
    account = boto3.client("sts").get_caller_identity()["Account"]
    region = os.environ.get("AWS_REGION", "")
    url = os.environ.get("PHONE_HOME_URL", "")
    preserve = os.environ.get("PRESERVE", "true").lower() == "true"

    # Scheduled re-tag (EventBridge) — no CloudFormation lifecycle.
    if "RequestType" not in event:
        rules = json.loads(os.environ.get("RULES", "[]"))
        tagged = apply_rules(client, rules, preserve)
        phone_home(url, {"event": "schedule", "account": account,
                         "region": region, "tagged": tagged,
                         "ceEnabled": cost_explorer_enabled(),
                         "codes": [r.get("productCode") for r in rules]})
        return

    import cfnresponse  # auto-available for inline CFN Lambdas

    request_type = event["RequestType"]
    props = event.get("ResourceProperties", {})
    try:
        if request_type == "Delete":
            if str(props.get("RemoveOnDelete", "false")).lower() == "true":
                remove_all(client)
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
            return
        rules = props.get("Rules", [])
        if isinstance(rules, str):  # advanced template passes a JSON string
            rules = json.loads(rules)
        tagged = apply_rules(client, rules, preserve)
        ce_ok = cost_explorer_enabled()
        phone_home(url, {"event": request_type, "account": account,
                         "region": region, "tagged": tagged, "ceEnabled": ce_ok,
                         "codes": [r.get("productCode") for r in rules]})
        cfnresponse.send(event, context, cfnresponse.SUCCESS,
                         {"tagged": tagged, "ceEnabled": ce_ok})
    except Exception as exc:  # noqa: BLE001 — surface any failure to CFN
        cfnresponse.send(event, context, cfnresponse.FAILED,
                         {"error": str(exc)[:300]})
