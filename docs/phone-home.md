# Phone-home (deployment telemetry)

The tagging templates can send a small **status beacon** to a URL you control, so
you (the partner) can track which customers have deployed tagging and whether they
meet both PRM requirements. This is opt-in: it only happens if you set the
`PhoneHomeUrl` parameter.

## What is sent

After each run (create, update, or scheduled re-tag) the tagging Lambda POSTs this
JSON:

```json
{
  "event": "Create",
  "account": "123456789012",
  "region": "us-east-1",
  "tagged": 212,
  "ceEnabled": true,
  "codes": ["aaa7sn1ne3t6nt2esgvyjmrg5"]
}
```

- `account` / `region` — where tagging ran.
- `tagged` — how many resources received the tag.
- `ceEnabled` — whether Cost Explorer (the second PRM requirement) is enabled.
- `codes` — the product code(s) used.

**No credentials, resource contents, ARNs, or cost figures are sent** — only the
counts and flags above.

## Receiver (your account)

[`templates/phone-home-receiver.yaml`](../templates/phone-home-receiver.yaml)
deploys a ready-made endpoint in **your own** AWS account:

```
API Gateway (HTTP API) -> Lambda -> DynamoDB table "prm-phone-home"
                                 \-> CloudWatch metrics (PRM/PhoneHome)
```

Deploy it:

```bash
aws cloudformation deploy \
  --template-file templates/phone-home-receiver.yaml \
  --stack-name prm-phone-home \
  --capabilities CAPABILITY_IAM \
  --region us-east-1
```

The stack output `PhoneHomeUrl` is the value you hand to customers as the tagging
template's `PhoneHomeUrl` parameter.

## Building a dashboard

Two ready sources:

- **DynamoDB** table `prm-phone-home` — one item per beacon, keyed by
  `pk = ACCT#<account>`, `sk = <region>#<epoch>`. Query the latest per account for a
  compliance table (tagged count + `ceEnabled`).
- **CloudWatch** namespace `PRM/PhoneHome` — metrics `ResourcesTagged` and
  `CostExplorerEnabled` per `Account` dimension. Drop these onto a CloudWatch
  dashboard for an at-a-glance view of who is tagged and who still needs Cost
  Explorer turned on.

## Forwarding to a CRM (e.g. Zoho)

To reflect status on a customer record in a CRM, extend the receiver Lambda to call
your CRM's API after `put_item` — map `account` to the customer/account record and
write `tagged` / `ceEnabled` / last-seen timestamp to custom fields. Keep CRM API
credentials in AWS Secrets Manager and grant the receiver role read access. (Left
out of the base template because it needs your CRM's OAuth credentials and field
mapping.)
