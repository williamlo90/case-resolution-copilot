# AWS Live Validation

Validation date: September 24, 2026

The repository's disposable AWS CDK environment was deployed to `ap-southeast-1`, validated, and
destroyed. This record supports the claim that the deployment path works on live AWS services. It
does not claim permanent production hosting or customer traffic on AWS.

## Passed Checks

- Foundation and Runtime CloudFormation stacks completed successfully.
- The CloudFront API health endpoint returned HTTP `200`.
- API, Celery worker, and Celery Beat scheduler reached stable ECS service state.
- The one-off Alembic migration task exited with code `0` at revision `20260813_0024`.
- PostgreSQL connectivity and the `pgvector` extension were verified from the running task.
- A versioned S3 input triggered Lambda validation and produced a content-addressed output manifest.
- Lambda delivered the validation request through SQS to the Celery worker.
- The connected Celery task recorded `aws_validation_passed` after querying RDS.
- The SQS dead-letter queue remained empty.
- ECR stored an immutable image digest after scanning; no critical or unapproved high findings were
  accepted.
- Both application stacks were destroyed and a post-teardown inventory found no application RDS,
  ALB, ECS, ECR, SQS, Lambda, CloudFront, Secrets Manager, scheduler, or Step Functions resources.

## Safety Boundary

- The always-on portfolio demo remains on Vercel with Neon PostgreSQL.
- Credentials were loaded from ignored local files into Secrets Manager and were not included in
  evidence or repository history.
- The environment used a cost-aware single-AZ profile and an AWS-side auto-destroy watchdog.
- This run validates deployment mechanics and the connected infrastructure path, not production
  availability, disaster recovery, sustained load, or customer data handling.
