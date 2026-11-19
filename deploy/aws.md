# AWS deployment

Verify account eligibility, credits, region and estimated charges before creating anything. No paid managed database or Kafka service is required. EC2, EBS, public IPv4, S3 requests and data transfer may incur charges. Set a budget alert (not a hard spending cap).

1. Create a private S3 bucket; keep Block Public Access enabled. Configure CORS for the exact HTTPS origin with POST and GET. Use an EC2 IAM role limited to the bucket's media prefix (GetObject, PutObject, DeleteObject). Do not put access keys on the instance.
2. Choose an EC2 instance only after measuring container memory locally. Allow inbound 443 and 80, restrict SSH to your IP. Require IMDSv2 and configure hop limit for container role access. Do not expose database or Redis ports.
3. Install Docker and Compose, copy the repository and configure `.env` with a strong database password, bucket, region, `SECURE_COOKIE=true`, `APP_ORIGIN=https://your-host`, `SITE_ADDRESS=your-host`, `HTTP_PORT=80`, `HTTPS_PORT=443`. A DNS hostname resolving to the instance is required for normal Caddy automatic HTTPS; do not send credentials over plain HTTP.
4. Run Compose, verify `/health`, provision accounts and test login, post creation, media upload, feed and engagement. Back up PostgreSQL to a protected location and test restoration. Stop or delete resources when no longer needed; check billing afterward.

Official references: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EC2_GetStarted.html and https://docs.aws.amazon.com/AmazonS3/latest/userguide/creating-bucket.html . Account-specific console choices and costs must be verified before deployment.
