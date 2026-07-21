# Status beacon (IAM-gated telemetry)

The tagging templates can send a small **status beacon** to the partner after each
run, so the partner can track which customers have deployed tagging and whether they
meet both PRM requirements (tagging + Cost Explorer). It's opt-in and **gated by
IAM** — there is no public endpoint.

## How the gate works

The partner deploys a cross-account IAM **role** in their own account. Its trust
policy allow-lists specific customer account ids and requires a shared external id.
The customer's tagging Lambda **assumes that role** and writes one record to the
partner's DynamoDB table. An account that is not in the trust policy is denied at
`sts:AssumeRole` and cannot write anything.

```
customer tagging Lambda --(sts:AssumeRole, ExternalId)--> partner role --> DynamoDB (partner acct)
        (only if the customer's account id is in the role trust policy)
```

Verified behaviour:
- Allow-listed account + correct external id → write succeeds.
- Allow-listed account + wrong external id → `AccessDenied`.
- Non-allow-listed account → `AccessDenied`.

## What is written

```json
{
  "pk": "ACCT#123456789012",
  "sk": "us-east-1#1737400000",
  "account": "123456789012",
  "region": "us-east-1",
  "event": "Create",
  "tagged": 212,
  "ceEnabled": true,
  "codes": "aaa7sn1ne3t6nt2esgvyjmrg5"
}
```

`tagged` = resources tagged; `ceEnabled` = whether Cost Explorer (the second PRM
requirement) is on; `codes` = product code(s) used. **No credentials, ARNs, resource
contents, or cost figures are sent.**

## Receiver (partner account)

[`templates/phone-home-role.yaml`](../templates/phone-home-role.yaml) deploys, in the
partner's own account:

- DynamoDB table `prm-phone-home` (pk = `ACCT#<account>`, sk = `<region>#<epoch>`)
- IAM role `prm-beacon-writer` with a trust policy allow-listing customer accounts +
  external id, granting only `dynamodb:PutItem` on that table

```bash
aws cloudformation deploy \
  --template-file templates/phone-home-role.yaml \
  --stack-name prm-phone-home \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1 \
  --parameter-overrides \
    'AllowedAccountIds=111111111111,222222222222' \
    ExternalId=your-shared-secret
```

Stack outputs give you the four values to hand each customer for the tagging
template's beacon parameters: `BeaconRoleArn`, `BeaconExternalId`, `BeaconTable`,
`BeaconRegion`.

**Onboarding a customer** = add their account id to `AllowedAccountIds` and update
the stack. **Scale ceiling:** account ids live in the role trust policy, which has a
2,048-character default limit (~50 accounts), raisable to 4,096 via Service Quotas
(~115), and unbounded by sharding across multiple roles. `aws:PrincipalOrgID` does
not help here because customers are outside the partner's AWS Organization.

## Identity and isolation

**Identifying who beaconed.** The beacon's `account` field is self-reported, which is
fine for a dashboard among trusted customers. If you ever need *authoritative* proof
of who called, it is already in **CloudTrail**: every `AssumeRole` event records the
real caller account, regardless of the payload and requiring no special permission in
the customer account. That is the portable, unforgeable source of identity.

**Why not session tags?** A tempting single-role design is to have the customer pass
their account as a session tag, bound in the trust policy via
`aws:RequestTag/customer == ${aws:PrincipalAccount}`, so the verified account rides
into the session as `aws:PrincipalTag/customer` and scopes `dynamodb:LeadingKeys`.
This was tested and rejected: passing a session tag requires **`sts:TagSession` in
the customer's account**, which an org SCP or permission boundary can deny (observed
in practice). Since the tool is handed to customers whose accounts we do not control,
session tags are not portable — a restricted customer would silently fail to beacon.
`sts:SourceIdentity` has the same caller-permission dependency; `RoleSessionName`
carries through with no extra permission but is caller-set and therefore spoofable.

**Hard isolation.** With a single shared role, every customer presents as the partner
account once assumed, so `dynamodb:LeadingKeys` cannot key on the caller's real
account and a (vetted, allow-listed) customer could in principle write another's
partition. The trust policy still strictly controls **who** may write at all — the
primary gate. If you need enforced per-customer isolation, deploy **one role per
customer** (plain `AssumeRole`, works everywhere): trust-scoped to a single account
with a hardcoded `LeadingKeys` condition, the role ARN being the identity. More roles
to manage, but airtight and dependency-free.

## Building a dashboard

- **DynamoDB** table `prm-phone-home` — one item per beacon; query latest per account
  for a compliance table (tagged count + `ceEnabled`).
- Add a small metrics-publishing Lambda on a DynamoDB stream, or a scheduled reader,
  to emit CloudWatch metrics and drive a CloudWatch dashboard.

## Forwarding to a CRM (e.g. Zoho)

Add a DynamoDB Stream trigger (or scheduled reader) that maps `account` to the
customer record in your CRM and writes `tagged` / `ceEnabled` / last-seen to custom
fields. Keep CRM API credentials in AWS Secrets Manager. Left out of the base
template because it needs your CRM's OAuth credentials and field mapping.
