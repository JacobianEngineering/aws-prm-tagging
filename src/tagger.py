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
- On CloudFormation Create/Update the handler tags matching resources.
- On a scheduled EventBridge invoke (event has no "RequestType") it re-applies the
  same rules — this catches resources created since the last run.
- On CloudFormation Delete it does nothing unless RemoveOnDelete is "true", in which
  case it removes the aws-apn-id tag from every resource that carries it. Default is
  to KEEP tags so revenue attribution is not interrupted by a stack deletion.

Per-resource tagging failures (e.g. Kubernetes pods, deleted snapshots) are returned
by the API in FailedResourcesMap and are intentionally ignored — they never fail the
stack.
"""
import json
import os

import boto3

TAG_KEY = "aws-apn-id"


def _get_arns(client, **filters):
    """Return all resource ARNs matching the given Tagging API filters."""
    arns, token = [], None
    while True:
        if token:
            filters["PaginationToken"] = token
        resp = client.get_resources(ResourcesPerPage=100, **filters)
        arns += [m["ResourceARN"] for m in resp["ResourceTagMappingList"]]
        token = resp.get("PaginationToken")
        if not token:
            break
    return arns


def _in_batches(arns, fn, size=20):
    """Apply fn to ARNs in batches (Tagging API allows 20 per call)."""
    for i in range(0, len(arns), size):
        fn(arns[i:i + size])


def apply_rules(client, rules):
    """Tag resources per the ordered rule list. Returns count tagged."""
    assigned, total = set(), 0
    for rule in rules:
        code = rule["productCode"]
        filters = {}
        if rule.get("resourceTypes"):
            filters["ResourceTypeFilters"] = rule["resourceTypes"]
        if rule.get("tagFilters"):
            filters["TagFilters"] = rule["tagFilters"]
        arns = [a for a in _get_arns(client, **filters) if a not in assigned]
        value = "pc:" + code
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
    """Remove the aws-apn-id tag from every resource that carries it."""
    arns = _get_arns(client, TagFilters=[{"Key": TAG_KEY}])
    _in_batches(
        arns,
        lambda batch: client.untag_resources(
            ResourceARNList=batch, TagKeys=[TAG_KEY]
        ),
    )
    return len(arns)


def handler(event, context):
    client = boto3.client("resourcegroupstaggingapi")

    # Scheduled re-tag (EventBridge) — no CloudFormation lifecycle.
    if "RequestType" not in event:
        apply_rules(client, json.loads(os.environ.get("RULES", "[]")))
        return

    import cfnresponse  # auto-available for inline CFN Lambdas

    request_type = event["RequestType"]
    props = event.get("ResourceProperties", {})
    rules = props.get("Rules", [])
    if isinstance(rules, str):  # advanced template passes rules as a JSON string
        rules = json.loads(rules)
    try:
        if request_type == "Delete":
            removed = 0
            if str(props.get("RemoveOnDelete", "false")).lower() == "true":
                removed = remove_all(client)
            cfnresponse.send(event, context, cfnresponse.SUCCESS,
                             {"removed": removed})
            return
        tagged = apply_rules(client, rules)
        cfnresponse.send(event, context, cfnresponse.SUCCESS,
                         {"tagged": tagged})
    except Exception as exc:  # noqa: BLE001 — surface any failure to CFN
        cfnresponse.send(event, context, cfnresponse.FAILED,
                         {"error": str(exc)[:300]})
