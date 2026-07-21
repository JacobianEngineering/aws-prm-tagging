# AWS PRM Resource Tagging — CloudFormation

CloudFormation templates that tag existing AWS resources for **AWS Partner Revenue
Measurement (PRM)**, so an AWS Partner can measure the AWS consumption their
solutions drive.

PRM attributes AWS spend to a partner when a resource carries the tag:

```
aws-apn-id = pc:<AWS Marketplace product code>
```

CloudFormation cannot natively tag resources it did not create, so these templates
deploy a small **Lambda-backed custom resource** that applies the tag through the
[AWS Resource Groups Tagging API](https://docs.aws.amazon.com/resourcegroupstagging/latest/APIReference/Welcome.html).
Everything is self-contained in one template — no S3 packaging, no build step.

> Not affiliated with or endorsed by AWS. Provided as-is under the MIT license.

## Templates

| Template | Use it when |
| --- | --- |
| [`templates/prm-tag-all.yaml`](templates/prm-tag-all.yaml) | You want to tag **every** supported resource in the account/region with **one** product code. |
| [`templates/prm-tag-by-rules.yaml`](templates/prm-tag-by-rules.yaml) | You want to split resources across **multiple** product codes by service/resource-type or by existing tags. |

Both accept an optional re-tag **schedule** (to catch newly created resources) and a
`RemoveOnDelete` flag.

## Quick start

### Option 1 — tag everything with one code

```bash
aws cloudformation deploy \
  --template-file templates/prm-tag-all.yaml \
  --stack-name prm-tagging \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides ProductCode=1xot9aw3srsz3tb25p2b17dmc
```

Add `ReTagSchedule='rate(1 day)'` to re-run daily and pick up new resources.

### Option 2 — tag by rule

Put your rules in a JSON string and pass them as the `TaggingRules` parameter:

```bash
RULES=$(tr -d '\n' < examples/rules-by-service.json)
aws cloudformation deploy \
  --template-file templates/prm-tag-by-rules.yaml \
  --stack-name prm-tagging \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides TaggingRules="$RULES"
```

You can also deploy either template from the AWS console: **CloudFormation → Create
stack → Upload a template file**.

## Rule format (advanced template)

`TaggingRules` is a JSON array. Rules are evaluated **in order**; each resource is
tagged by the **first** rule it matches, because a resource can carry only one
`aws-apn-id` tag.

```json
[
  { "productCode": "PENTEST_CODE",     "tagFilters":    [{ "Key": "PublicFacing", "Values": ["true"] }] },
  { "productCode": "COMPLIANCE_CODE",  "resourceTypes": ["rds:db", "dynamodb:table"] },
  { "productCode": "MANAGED_SVC_CODE" }
]
```

Each rule:

| Field | Required | Meaning |
| --- | --- | --- |
| `productCode` | yes | The Marketplace product code (the tag becomes `pc:<productCode>`). |
| `resourceTypes` | no | List of Tagging-API resource-type filters, e.g. `ec2:instance`, `rds:db`, `s3`. Omit to match all types. |
| `tagFilters` | no | List of `{ "Key": ..., "Values": [...] }` filters on **existing** tags. Omit to match regardless of tags. A key with no values matches any value. |

- A rule with neither `resourceTypes` nor `tagFilters` matches **every** taggable
  resource — put it **last** as a catch-all.
- The example above sends anything already tagged `PublicFacing=true` to a
  penetration-testing code, databases to a compliance code, and everything else to
  a managed-services code.

See [`examples/`](examples/) for ready-to-edit rule sets, and
[`docs/rule-recipes.md`](docs/rule-recipes.md) for more patterns (public-facing
selection, environment split, per-service split).

## What resources get tagged

Attribution is only surfaced for AWS's
[PRM resource-tagging supported services](https://docs.aws.amazon.com/PRM/latest/aws-prm-onboarding-guide/resource-tagging-included-services.html)
(EC2/EBS, RDS, S3 storage, Lambda, DynamoDB, ELB, EFS, EKS, ECS, CloudFront, API
Gateway, Bedrock, CloudWatch Logs, AWS Backup, Secrets Manager, and more — ~90
services). The templates attempt to tag whatever matches your rules; resource types
that don't support tagging simply fail silently for that resource and never fail the
stack.

## Options

| Parameter | Default | Notes |
| --- | --- | --- |
| `ReTagSchedule` | `""` (off) | EventBridge schedule expression, e.g. `rate(1 day)` or `cron(0 6 * * ? *)`. Re-runs tagging to catch new resources. |
| `RemoveOnDelete` | `false` | If `true`, deleting the stack removes the `aws-apn-id` tag from all resources. Default keeps tags so **attribution is not interrupted** by a stack deletion. |

## Notes and caveats

- **One partner per resource.** Only one `aws-apn-id` tag is allowed per resource.
  Rule order decides which code wins.
- **IaC drift.** If a resource is managed by CloudFormation/Terraform/CDK, tagging
  it out-of-band can show as drift, and a later `apply` can strip the tag. Prefer
  adding `aws-apn-id` to your IaC default tags, or use `ReTagSchedule` to
  re-apply regularly. Attribution stops the month a tag disappears.
- **Per-region.** The Tagging API is regional. Deploy the stack in each region you
  operate in.
- **IAM scope.** The Lambda role grants tag actions across many services with
  `Resource: "*"` — cross-service tagging can't be resource-scoped in practice.
  Review [`templates/prm-tag-all.yaml`](templates/prm-tag-all.yaml) and trim the
  action list to the services you actually use if you want tighter least-privilege.
- **Cost.** The Lambda runs briefly on stack create/update (and on the optional
  schedule). Effectively negligible.

## How it works

1. The stack creates an IAM role and a Python Lambda (source:
   [`src/tagger.py`](src/tagger.py); a byte-compact copy is inlined in each
   template).
2. A `Custom::PrmTagger` resource invokes the Lambda on create/update. The Lambda
   enumerates resources via `GetResources` and applies the tag via `TagResources`
   in batches.
3. If a schedule is set, an EventBridge rule re-invokes the Lambda periodically to
   tag resources created since the last run.
4. On stack delete, the Lambda removes tags only if `RemoveOnDelete=true`.

## Verifying

```bash
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=aws-apn-id \
  --query 'ResourceTagMappingList[].{ARN:ResourceARN,Tags:Tags}'
```

## License

[MIT](LICENSE).
