# Tag your AWS resources for Jacobian Engineering (AWS PRM)

This repository gives you a one-click **AWS CloudFormation** template that tags the
AWS resources Jacobian Engineering helps you run, so that AWS can correctly measure
the value of that work under **AWS Partner Revenue Measurement (PRM)**. It costs you
nothing, changes none of your resources except adding one tag, and takes a few
minutes.

**Need help? We'll do it with you or for you.**
📧 support@jacobianengineering.com &nbsp;•&nbsp; ☎️ (415) 644-8208 &nbsp;•&nbsp; 🌐 [jacobianengineering.com](https://jacobianengineering.com)

---

## What this does

It adds a single AWS tag to your resources:

```
aws-apn-id = pc:<Jacobian Engineering product code>
```

That tag is how AWS attributes the AWS usage we help you operate to Jacobian
Engineering. It does **not** grant anyone access to your account, move data, or
change how your resources run. (CloudFormation can't tag existing resources on its
own, so the template installs a small helper function that applies the tags for
you and then sits idle.)

## Before you start (2 things)

AWS PRM has **two** requirements. This template handles the first and checks the
second:

1. **Resource tagging** — done by this template. ✅
2. **Cost Explorer must be enabled** in your account. The template detects whether
   it's on and reports the result, but AWS provides no way to turn it on
   automatically. If it's off, enable it once (takes 10 seconds, no cost to view):
   **AWS Console → Billing and Cost Management → Cost Explorer → Launch Cost
   Explorer.** More: [Enabling Cost Explorer](https://docs.aws.amazon.com/cost-management/latest/userguide/ce-enable.html).

If you're not sure, email us and we'll confirm both for you.

## Which template to use

| Template | Use it when |
| --- | --- |
| [`templates/prm-tag-all.yaml`](templates/prm-tag-all.yaml) | **Most customers.** Tag everything with one Jacobian service code. |
| [`templates/prm-tag-by-rules.yaml`](templates/prm-tag-by-rules.yaml) | You use more than one Jacobian service and want to split resources between them. |

Your Jacobian contact will tell you which product code(s) to use. They're also
listed in [`docs/jacobian-product-codes.md`](docs/jacobian-product-codes.md).

## How to deploy (console, ~3 minutes)

1. Sign in to the [AWS CloudFormation console](https://console.aws.amazon.com/cloudformation/)
   in the **region** where your resources run. (Repeat for each region if you use
   more than one.)
2. **Create stack → With new resources (standard)**.
3. **Upload a template file** → choose `templates/prm-tag-all.yaml` from this repo →
   **Next**.
4. **Stack name:** `jacobian-prm-tagging`. **ProductCode:** the code we gave you.
   Leave the other options at their defaults. **Next → Next**.
5. Check the box **"I acknowledge that AWS CloudFormation might create IAM
   resources"** → **Submit**.
6. When the stack shows **CREATE_COMPLETE**, you're done. The **Outputs** tab shows
   the tag that was applied.

Prefer the command line?

```bash
aws cloudformation deploy \
  --template-file templates/prm-tag-all.yaml \
  --stack-name jacobian-prm-tagging \
  --capabilities CAPABILITY_IAM \
  --region us-east-1 \
  --parameter-overrides ProductCode=PASTE_CODE_HERE
```

## Options (all optional)

| Option | Default | What it does |
| --- | --- | --- |
| `PreserveExistingTags` | `true` | **Won't overwrite another partner's tag.** If a resource already has an `aws-apn-id` tag from a different vendor, it's left alone. Set `false` only if you intend to reassign everything to Jacobian. |
| `ReTagSchedule` | `rate(1 day)` (on) | Re-runs tagging on a schedule so resources you create later get tagged too, and tags stripped by an IaC deploy get re-applied. On by default (daily). Set to an empty string to turn it off. |
| `PreserveTagsOnDelete` | `true` | If you delete the stack, the tags are **left in place** by default so attribution isn't interrupted. Set `false` to also remove the tags on stack deletion. |
| `BeaconRoleArn` (+ `BeaconExternalId`, `BeaconTable`, `BeaconRegion`) | off | If Jacobian gives you these values, the template sends us a small status note (your account id, region, how many resources were tagged, and whether Cost Explorer is on) so we can confirm everything worked. It works by assuming an IAM role **we** control — nothing is sent unless you fill these in, and no resource data or credentials are ever sent. See [`docs/phone-home.md`](docs/phone-home.md). |

## Does this overwrite tags from my other vendors?

**No, not by default.** A resource can only carry one `aws-apn-id` tag, so PRM allows
one partner per resource. This template **skips** any resource that already has a
different partner's `aws-apn-id` tag (`PreserveExistingTags=true`, the default). If
you work with multiple AWS partners, use the rule-based template to divide resources
deliberately, and talk to us first. See
[`docs/rule-recipes.md`](docs/rule-recipes.md).

## Verifying

In the CloudFormation **Outputs** tab you'll see the tag applied and the Cost
Explorer status. To list tagged resources yourself:

```bash
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=aws-apn-id \
  --query 'ResourceTagMappingList[].ResourceARN'
```

## Good to know

- **Per region.** Deploy once per AWS region you use.
- **Infrastructure-as-code drift.** If you manage resources with Terraform/CDK/
  CloudFormation of your own, a future deploy could strip the tag. The daily
  `ReTagSchedule` (on by default) re-applies it automatically; for a permanent fix,
  add `aws-apn-id` to your own default tags. (We're happy to advise.)
- **Cost.** The helper function runs for a few seconds. Effectively free.
- **Removing it.** Delete the `jacobian-prm-tagging` stack anytime. By default the
  tags remain (`PreserveTagsOnDelete=true`); set it to `false` first if you want them
  gone.

## For engineers: how it works

The stack creates an IAM role and a small Python Lambda (readable source:
[`src/tagger.py`](src/tagger.py); a byte-compact copy is inlined in each template so
the template is fully self-contained — no S3 packaging). A `Custom::PrmTagger`
resource invokes it on create/update: it enumerates resources through the
[Resource Groups Tagging API](https://docs.aws.amazon.com/resourcegroupstagging/latest/APIReference/Welcome.html),
skips resources already tagged for another partner, applies the tag in batches,
checks Cost Explorer, and optionally writes a status beacon (by assuming a partner
role). An optional EventBridge
schedule re-runs it to catch new resources.

Partners: [`templates/phone-home-role.yaml`](templates/phone-home-role.yaml) deploys
an IAM-gated receiver in your own account — a cross-account role (trust policy
allow-lists customer account ids + external id) that customers assume to write status
beacons to your DynamoDB table. No public endpoint. See
[`docs/phone-home.md`](docs/phone-home.md).

## License

[MIT](LICENSE). Provided as-is; not affiliated with or endorsed by AWS.
