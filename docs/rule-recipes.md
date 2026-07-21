# Rule recipes

Copy-paste starting points for the `TaggingRules` parameter of
[`prm-tag-by-rules.yaml`](../templates/prm-tag-by-rules.yaml). Replace the
`*_CODE` placeholders with your own AWS Marketplace product codes.

Rules are evaluated **in order**; each resource is tagged by the **first** rule it
matches. Put broad catch-alls last.

## Everything to one code (equivalent to the simple template)

```json
[ { "productCode": "MANAGED_SVC_CODE" } ]
```

## Public-facing edge to a pen-test code, rest to managed services

Matches resources you have tagged `PublicFacing=true`, plus the usual internet-facing
resource types, then everything else.

```json
[
  { "productCode": "PENTEST_CODE",    "tagFilters": [{ "Key": "PublicFacing", "Values": ["true"] }] },
  { "productCode": "PENTEST_CODE",    "resourceTypes": ["cloudfront:distribution", "elasticloadbalancing:loadbalancer", "apigateway:restapis"] },
  { "productCode": "MANAGED_SVC_CODE" }
]
```

## Split by service line

```json
[
  { "productCode": "COMPLIANCE_CODE", "resourceTypes": ["rds:db", "dynamodb:table", "backup:backup-vault"] },
  { "productCode": "AI_CODE",         "resourceTypes": ["bedrock:agent", "sagemaker:endpoint"] },
  { "productCode": "MANAGED_SVC_CODE" }
]
```

## Only production resources

Tags nothing that isn't marked production. No catch-all, so dev/test is left
untagged.

```json
[
  { "productCode": "MANAGED_SVC_CODE", "tagFilters": [{ "Key": "Environment", "Values": ["prod", "production"] }] }
]
```

## Combine a tag filter with a type filter

A single rule ANDs its `resourceTypes` and `tagFilters`. This tags only RDS
databases that are also tagged `Tier=regulated`.

```json
[
  { "productCode": "COMPLIANCE_CODE", "resourceTypes": ["rds:db"], "tagFilters": [{ "Key": "Tier", "Values": ["regulated"] }] }
]
```

## Resource-type filter reference

`resourceTypes` values are AWS Resource Groups Tagging API resource-type filters,
usually `service:type` (or just `service`). Common ones:

| Filter | Resource |
| --- | --- |
| `ec2:instance` | EC2 instances |
| `ec2:volume` | EBS volumes |
| `ec2:snapshot` | EBS snapshots |
| `rds:db` | RDS instances |
| `rds:cluster` | Aurora/RDS clusters |
| `dynamodb:table` | DynamoDB tables |
| `s3` | S3 buckets |
| `lambda:function` | Lambda functions |
| `elasticloadbalancing:loadbalancer` | ALB/NLB |
| `eks:cluster` | EKS clusters |
| `ecs:cluster` / `ecs:service` | ECS clusters / services |
| `elasticfilesystem:file-system` | EFS |
| `cloudfront:distribution` | CloudFront |
| `apigateway:restapis` | API Gateway REST APIs |
| `backup:backup-vault` | AWS Backup vaults |
| `secretsmanager:secret` | Secrets Manager secrets |

To discover the exact filter for a resource type, look at the `service:` prefix of
its ARN, or run:

```bash
aws resourcegroupstaggingapi get-resources --resource-type-filters ec2:instance
```
