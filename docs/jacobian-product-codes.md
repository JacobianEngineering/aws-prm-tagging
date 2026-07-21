# Jacobian Engineering — AWS Marketplace product codes

These are the AWS Marketplace product codes for Jacobian Engineering's service
listings, for use as the `pc:<code>` value when tagging resources that Jacobian
operates for a customer. They are public identifiers (they appear on the public
AWS Marketplace listing pages and inside the tags applied to customer resources).

> If you are a different AWS Partner using these templates, ignore this file and use
> **your own** product codes from your AWS Marketplace Management Portal
> (Products → your product → Product Summary). Tagging with someone else's code
> attributes your AWS spend to them.

| Service line | Product code |
| --- | --- |
| Manual Penetration Testing of Web Applications and APIs | `1xot9aw3srsz3tb25p2b17dmc` |
| SOC 2 Readiness | `3zvbeiadtjc3xumf7lemr7hbl` |
| Managed Services – Cloud and IT Operations | `aaa7sn1ne3t6nt2esgvyjmrg5` |
| Managed Compliance Services – DevSecOps | `bjmq481ji0k90szjt11sjwt4q` |
| AI Managed Services – Voice, Operations, Agentic and Generative AI | `1wxvhnewwgj2vw5w1nabd81j6` |

Find all listings on the
[Jacobian Engineering AWS Marketplace seller profile](https://aws.amazon.com/marketplace/seller-profile?id=seller-zec7tpsbfyf7k).

## Example: tag everything with Managed Services

```bash
aws cloudformation deploy \
  --template-file templates/prm-tag-all.yaml \
  --stack-name prm-tagging \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides ProductCode=aaa7sn1ne3t6nt2esgvyjmrg5
```

## Example: split compliance vs managed services

```json
[
  { "productCode": "bjmq481ji0k90szjt11sjwt4q", "resourceTypes": ["rds:db", "dynamodb:table", "backup:backup-vault", "guardduty:detector"] },
  { "productCode": "aaa7sn1ne3t6nt2esgvyjmrg5" }
]
```
