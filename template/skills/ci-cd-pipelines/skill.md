# CI/CD Pipelines Skill

Advanced continuous integration and deployment expertise covering modern CI/CD platforms, pipeline optimization, security integration, and enterprise-grade automation.

## Skill Overview

Expert CI/CD knowledge including GitHub Actions, GitLab CI, Jenkins, Azure DevOps, pipeline security, deployment strategies, infrastructure automation, and DevSecOps integration using cutting-edge tools and methodologies.

## Core Capabilities

### Pipeline Architecture
- **Multi-stage pipelines** - Build, test, security, deploy with proper gating
- **Matrix strategies** - Cross-platform testing, multi-environment deployment
- **Pipeline orchestration** - Complex workflow dependencies, parallel execution
- **Deployment strategies** - Blue-green, canary, rolling, feature flags

### Security Integration
- **DevSecOps** - Security scanning, compliance checks, vulnerability assessment
- **Secret management** - Vault integration, rotation policies, least privilege
- **Code signing** - Artifact verification, supply chain security
- **Compliance automation** - SOX, PCI, HIPAA automated validation

### Performance & Optimization
- **Pipeline optimization** - Caching strategies, build acceleration, resource management
- **Artifact management** - Registry optimization, cleanup policies, versioning
- **Cost optimization** - Resource rightsizing, spot instance usage, build efficiency
- **Monitoring & observability** - Pipeline metrics, failure analysis, performance tracking

### Enterprise Features
- **Multi-cloud deployment** - AWS, Azure, GCP automated deployment
- **Infrastructure provisioning** - Terraform automation, environment management
- **Release management** - Automated rollbacks, approval workflows, change tracking
- **Disaster recovery** - Pipeline backup, cross-region deployment, failover automation

## Modern CI/CD Implementation

### GitHub Actions Advanced Workflows
```yaml
# Advanced GitHub Actions workflow with security and optimization
name: Production Deployment Pipeline
on:
  push:
    branches: [main]
    paths-ignore:
      - 'docs/**'
      - '*.md'
  pull_request:
    branches: [main]
  schedule:
    # Daily security scan
    - cron: '0 2 * * *'
  workflow_dispatch:
    inputs:
      environment:
        description: 'Deployment environment'
        required: true
        default: 'staging'
        type: choice
        options:
          - staging
          - production
      skip_tests:
        description: 'Skip tests'
        type: boolean
        default: false

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}
  NODE_VERSION: '20.x'
  DOCKER_BUILDKIT: 1

# Global permissions for security
permissions:
  contents: read
  packages: write
  security-events: write
  id-token: write  # For OIDC

jobs:
  # Job 1: Code Quality and Security Analysis
  code-analysis:
    name: 🔍 Code Analysis
    runs-on: ubuntu-latest
    outputs:
      cache-key: ${{ steps.cache.outputs.cache-hit }}
      security-passed: ${{ steps.security-scan.outputs.passed }}
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for better analysis

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'

      - name: Cache dependencies
        id: cache
        uses: actions/cache@v3
        with:
          path: |
            ~/.npm
            node_modules
            .next/cache
          key: ${{ runner.os }}-node-${{ hashFiles('**/package-lock.json') }}
          restore-keys: |
            ${{ runner.os }}-node-

      - name: Install dependencies
        run: npm ci --prefer-offline --no-audit

      - name: TypeScript compilation check
        run: npm run type-check

      - name: Lint with ESLint
        run: npm run lint -- --format=sarif --output-file=eslint-results.sarif
        continue-on-error: true

      - name: Format check with Prettier
        run: npm run format:check

      - name: Security audit
        run: npm audit --audit-level moderate

      - name: CodeQL Analysis
        uses: github/codeql-action/init@v2
        with:
          languages: javascript
          config-file: ./.github/codeql/codeql-config.yml

      - name: Autobuild
        uses: github/codeql-action/autobuild@v2

      - name: Perform CodeQL Analysis
        uses: github/codeql-action/analyze@v2

      - name: Run Semgrep Security Scan
        id: security-scan
        uses: returntocorp/semgrep-action@v1
        with:
          config: >-
            p/security-audit
            p/secrets
            p/owasp-top-ten
            p/react
            p/typescript
        env:
          SEMGREP_APP_TOKEN: ${{ secrets.SEMGREP_APP_TOKEN }}

      - name: Upload SARIF files
        uses: github/codeql-action/upload-sarif@v2
        if: always()
        with:
          sarif_file: |
            eslint-results.sarif
            semgrep.sarif

  # Job 2: Comprehensive Testing
  testing:
    name: 🧪 Testing Suite
    runs-on: ubuntu-latest
    needs: code-analysis
    if: ${{ !inputs.skip_tests }}
    strategy:
      matrix:
        test-suite: [unit, integration, e2e]
        node-version: ['18.x', '20.x']
      fail-fast: false
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 3s
          --health-retries 5
        ports:
          - 6379:6379

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Node.js ${{ matrix.node-version }}
        uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node-version }}
          cache: 'npm'

      - name: Restore dependencies cache
        uses: actions/cache@v3
        with:
          path: |
            ~/.npm
            node_modules
          key: ${{ runner.os }}-node-${{ hashFiles('**/package-lock.json') }}

      - name: Install dependencies
        run: npm ci

      - name: Setup test environment
        run: |
          cp .env.test.example .env.test
          npm run db:migrate
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db
          REDIS_URL: redis://localhost:6379

      - name: Run unit tests
        if: matrix.test-suite == 'unit'
        run: |
          npm run test:unit -- --coverage --coverageReporters=json-summary --coverageReporters=lcov
        env:
          CI: true

      - name: Run integration tests
        if: matrix.test-suite == 'integration'
        run: npm run test:integration
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db
          REDIS_URL: redis://localhost:6379

      - name: Run E2E tests
        if: matrix.test-suite == 'e2e'
        run: |
          npm run build
          npm run test:e2e
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db
          PLAYWRIGHT_BROWSERS_PATH: 0

      - name: Upload coverage to Codecov
        if: matrix.test-suite == 'unit' && matrix.node-version == '20.x'
        uses: codecov/codecov-action@v3
        with:
          token: ${{ secrets.CODECOV_TOKEN }}
          files: ./coverage/lcov.info
          flags: unittests
          name: codecov-umbrella
          fail_ci_if_error: true

      - name: Upload test artifacts
        uses: actions/upload-artifact@v3
        if: failure()
        with:
          name: test-artifacts-${{ matrix.test-suite }}-${{ matrix.node-version }}
          path: |
            test-results/
            playwright-report/
            coverage/

  # Job 3: Container Build and Security Scan
  container-build:
    name: 🐳 Container Build & Scan
    runs-on: ubuntu-latest
    needs: [code-analysis, testing]
    outputs:
      image: ${{ steps.image.outputs.image }}
      digest: ${{ steps.build.outputs.digest }}
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
        with:
          platforms: linux/amd64,linux/arm64

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=sha,prefix={{branch}}-
            type=raw,value=latest,enable={{is_default_branch}}
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}

      - name: Build and push Docker image
        id: build
        uses: docker/build-push-action@v5
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          build-args: |
            NODE_VERSION=${{ env.NODE_VERSION }}
            BUILD_DATE=${{ github.event.head_commit.timestamp }}
            VCS_REF=${{ github.sha }}

      - name: Generate SBOM
        uses: anchore/sbom-action@v0
        with:
          image: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          format: spdx-json
          output-file: sbom.spdx.json

      - name: Scan container with Trivy
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          format: 'sarif'
          output: 'trivy-results.sarif'

      - name: Upload Trivy scan results
        uses: github/codeql-action/upload-sarif@v2
        if: always()
        with:
          sarif_file: 'trivy-results.sarif'

      - name: Run Snyk to check Docker image vulnerabilities
        uses: snyk/actions/docker@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
        with:
          image: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          args: --severity-threshold=high

      - name: Sign container image with cosign
        if: github.event_name != 'pull_request'
        uses: sigstore/cosign-installer@v3.1.1

      - name: Sign the images with GitHub OIDC Token
        if: github.event_name != 'pull_request'
        env:
          COSIGN_EXPERIMENTAL: 1
        run: |
          echo "${{ steps.meta.outputs.tags }}" | xargs -I {} cosign sign --yes {}@${{ steps.build.outputs.digest }}

      - name: Set image output
        id: image
        run: echo "image=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}" >> $GITHUB_OUTPUT

  # Job 4: Infrastructure as Code
  infrastructure:
    name: 🏗️ Infrastructure Deployment
    runs-on: ubuntu-latest
    needs: container-build
    if: github.ref == 'refs/heads/main' || github.event_name == 'workflow_dispatch'
    environment:
      name: ${{ inputs.environment || 'staging' }}
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: us-west-2
          role-session-name: GitHubActions

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.6.0

      - name: Terraform Init
        run: terraform init
        working-directory: infrastructure/

      - name: Terraform Plan
        id: plan
        run: |
          terraform plan -var="image_tag=${{ github.sha }}" -var="environment=${{ inputs.environment || 'staging' }}" -out=tfplan
        working-directory: infrastructure/

      - name: Terraform Apply
        if: github.ref == 'refs/heads/main' && (inputs.environment == 'production' || inputs.environment == 'staging')
        run: terraform apply tfplan
        working-directory: infrastructure/

      - name: Output infrastructure details
        if: always()
        run: terraform output -json > infrastructure-outputs.json
        working-directory: infrastructure/

      - name: Upload infrastructure artifacts
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: infrastructure-${{ inputs.environment || 'staging' }}
          path: |
            infrastructure/tfplan
            infrastructure/infrastructure-outputs.json

  # Job 5: Application Deployment
  deploy:
    name: 🚀 Application Deployment
    runs-on: ubuntu-latest
    needs: [container-build, infrastructure]
    if: github.ref == 'refs/heads/main' || github.event_name == 'workflow_dispatch'
    environment:
      name: ${{ inputs.environment || 'staging' }}
      url: ${{ steps.deploy.outputs.url }}
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: us-west-2

      - name: Setup kubectl
        uses: azure/setup-kubectl@v3
        with:
          version: 'v1.28.0'

      - name: Update kubeconfig
        run: |
          aws eks update-kubeconfig --name production-cluster --region us-west-2

      - name: Deploy to Kubernetes
        id: deploy
        run: |
          # Update image tag in deployment
          sed -i "s|{{IMAGE_TAG}}|${{ github.sha }}|g" k8s/deployment.yaml

          # Apply Kubernetes manifests
          kubectl apply -f k8s/

          # Wait for deployment to complete
          kubectl rollout status deployment/app-deployment --timeout=600s

          # Get service URL
          SERVICE_URL=$(kubectl get svc app-service -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
          echo "url=https://${SERVICE_URL}" >> $GITHUB_OUTPUT

      - name: Run smoke tests
        run: |
          # Wait for service to be ready
          sleep 30

          # Run health check
          curl -f ${{ steps.deploy.outputs.url }}/health || exit 1

          # Run basic functionality tests
          npm run test:smoke -- --baseUrl=${{ steps.deploy.outputs.url }}

      - name: Setup monitoring
        run: |
          # Deploy monitoring resources
          kubectl apply -f monitoring/

          # Configure alerts
          kubectl apply -f alerts/

  # Job 6: Performance & Load Testing
  performance-testing:
    name: ⚡ Performance Testing
    runs-on: ubuntu-latest
    needs: deploy
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup k6
        run: |
          sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
          echo "deb https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
          sudo apt-get update
          sudo apt-get install k6

      - name: Run load tests
        run: |
          k6 run --out json=results.json performance/load-test.js
        env:
          BASE_URL: ${{ needs.deploy.outputs.url }}

      - name: Analyze performance results
        run: |
          node performance/analyze-results.js results.json

      - name: Upload performance artifacts
        uses: actions/upload-artifact@v3
        with:
          name: performance-results
          path: |
            results.json
            performance-report.html

  # Job 7: Security & Compliance Validation
  security-compliance:
    name: 🔒 Security & Compliance
    runs-on: ubuntu-latest
    needs: deploy
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Run OWASP ZAP security scan
        uses: zaproxy/action-full-scan@v0.7.0
        with:
          target: ${{ needs.deploy.outputs.url }}
          rules_file_name: '.zap/rules.tsv'
          cmd_options: '-a'
          allow_issue_writing: false

      - name: Run compliance checks
        run: |
          # Check SSL/TLS configuration
          echo | openssl s_client -servername $(echo ${{ needs.deploy.outputs.url }} | sed 's|https://||') -connect $(echo ${{ needs.deploy.outputs.url }} | sed 's|https://||'):443 2>/dev/null | openssl x509 -noout -dates

          # Check security headers
          curl -I ${{ needs.deploy.outputs.url }} | grep -E "(X-Frame-Options|X-Content-Type-Options|Strict-Transport-Security)"

      - name: Generate compliance report
        run: |
          node scripts/generate-compliance-report.js > compliance-report.json

      - name: Upload security artifacts
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: security-compliance
          path: |
            compliance-report.json
            zap-report.html

  # Job 8: Notification & Cleanup
  notification:
    name: 📢 Notifications
    runs-on: ubuntu-latest
    needs: [deploy, performance-testing, security-compliance]
    if: always()
    steps:
      - name: Notify Slack on success
        if: success()
        uses: 8398a7/action-slack@v3
        with:
          status: success
          channel: '#deployments'
          text: |
            ✅ Deployment successful to ${{ inputs.environment || 'staging' }}
            🔗 URL: ${{ needs.deploy.outputs.url }}
            📊 Performance: All tests passed
            🔒 Security: No critical issues found
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}

      - name: Notify Slack on failure
        if: failure()
        uses: 8398a7/action-slack@v3
        with:
          status: failure
          channel: '#deployments'
          text: |
            ❌ Deployment failed to ${{ inputs.environment || 'staging' }}
            🔍 Check: https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }}
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}

      - name: Cleanup on failure
        if: failure() && github.ref == 'refs/heads/main'
        run: |
          # Rollback deployment if needed
          kubectl rollout undo deployment/app-deployment

          # Clean up failed resources
          kubectl delete pods --field-selector=status.phase=Failed

# Reusable workflows for other repositories
  call-reusable-workflow:
    name: 🔄 Reusable Workflows
    uses: ./.github/workflows/shared-pipeline.yml
    with:
      environment: ${{ inputs.environment || 'staging' }}
      skip-tests: ${{ inputs.skip_tests }}
    secrets:
      inherit
```

### GitLab CI Advanced Pipeline
```yaml
# Advanced GitLab CI pipeline with comprehensive DevSecOps
stages:
  - validate
  - build
  - security-scan
  - test
  - package
  - deploy-staging
  - security-test
  - deploy-production
  - monitor

variables:
  # Global variables
  DOCKER_DRIVER: overlay2
  DOCKER_TLS_CERTDIR: "/certs"
  REGISTRY: $CI_REGISTRY_IMAGE
  KUBERNETES_NAMESPACE: "production"

  # Feature flags
  FF_USE_FASTZIP: "true"
  FF_KUBERNETES_HONOR_ENTRYPOINT: "true"

# Global configuration
default:
  image: alpine/git:latest
  before_script:
    - echo "Pipeline started at $(date)"
  after_script:
    - echo "Pipeline step completed at $(date)"

# Templates for reusability
.docker_template: &docker_config
  image: docker:20.10.16
  services:
    - docker:20.10.16-dind
  before_script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY

.kubectl_template: &kubectl_config
  image: bitnami/kubectl:1.28
  before_script:
    - kubectl config use-context $CI_PROJECT_PATH:production

.node_template: &node_config
  image: node:20-alpine
  cache:
    key: npm-cache
    paths:
      - node_modules/
      - .npm/
  before_script:
    - npm ci --cache .npm --prefer-offline

# Stage 1: Validation
code-quality:
  stage: validate
  <<: *node_config
  script:
    - npm run lint
    - npm run type-check
    - npm run format:check
  artifacts:
    reports:
      junit: reports/junit.xml
    paths:
      - reports/
  rules:
    - if: '$CI_PIPELINE_SOURCE == "push"'
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'

dependency-scan:
  stage: validate
  <<: *node_config
  script:
    - npm audit --audit-level moderate
    - npx license-checker --onlyAllow "MIT;Apache-2.0;BSD-2-Clause;BSD-3-Clause;ISC"
  allow_failure: true

secret-detection:
  stage: validate
  image: returntocorp/semgrep:latest
  script:
    - semgrep --config=p/secrets --json --output=secrets-report.json .
  artifacts:
    reports:
      sast: secrets-report.json
  allow_failure: true

# Stage 2: Build
build-application:
  stage: build
  <<: *node_config
  script:
    - npm run build
    - npm run build:storybook
  artifacts:
    expire_in: 1 hour
    paths:
      - dist/
      - storybook-static/
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'

# Stage 3: Security Scanning
sast-scan:
  stage: security-scan
  include:
    - template: Security/SAST.gitlab-ci.yml
  variables:
    SAST_EXPERIMENTAL_FEATURES: "true"

dependency-scanning:
  stage: security-scan
  include:
    - template: Security/Dependency-Scanning.gitlab-ci.yml

container-scanning:
  stage: security-scan
  include:
    - template: Security/Container-Scanning.gitlab-ci.yml
  variables:
    CS_IMAGE: $REGISTRY:$CI_COMMIT_SHA
  needs:
    - build-docker-image

license-scanning:
  stage: security-scan
  include:
    - template: Security/License-Scanning.gitlab-ci.yml

# Stage 4: Testing
unit-tests:
  stage: test
  <<: *node_config
  services:
    - postgres:15
    - redis:7-alpine
  variables:
    POSTGRES_DB: test_db
    POSTGRES_USER: postgres
    POSTGRES_PASSWORD: postgres
    DATABASE_URL: postgres://postgres:postgres@postgres:5432/test_db
    REDIS_URL: redis://redis:6379
  script:
    - npm run test:unit -- --coverage --ci
  coverage: '/Lines\s*:\s*(\d+\.\d+)%/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage/cobertura-coverage.xml
      junit: reports/junit.xml
    paths:
      - coverage/

integration-tests:
  stage: test
  <<: *node_config
  services:
    - postgres:15
    - redis:7-alpine
  variables:
    DATABASE_URL: postgres://postgres:postgres@postgres:5432/test_db
    REDIS_URL: redis://redis:6379
  script:
    - npm run db:migrate
    - npm run test:integration
  artifacts:
    when: on_failure
    paths:
      - logs/

e2e-tests:
  stage: test
  image: mcr.microsoft.com/playwright:v1.40.0-focal
  needs:
    - build-application
  script:
    - npm ci
    - npm run test:e2e
  artifacts:
    when: on_failure
    paths:
      - playwright-report/
      - test-results/
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'

# Stage 5: Package
build-docker-image:
  stage: package
  <<: *docker_config
  needs:
    - build-application
  script:
    # Multi-stage build with security scanning
    - |
      docker build \
        --build-arg NODE_VERSION=20 \
        --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
        --build-arg VCS_REF=$CI_COMMIT_SHA \
        --cache-from $REGISTRY:cache \
        --tag $REGISTRY:$CI_COMMIT_SHA \
        --tag $REGISTRY:latest \
        .

    # Security scan with Trivy
    - docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest image --format json --output trivy-report.json $REGISTRY:$CI_COMMIT_SHA

    # Push images
    - docker push $REGISTRY:$CI_COMMIT_SHA
    - docker push $REGISTRY:latest
  artifacts:
    reports:
      container_scanning: trivy-report.json
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'

sign-image:
  stage: package
  image: gcr.io/projectsigstore/cosign:v2.0.0
  needs:
    - build-docker-image
  script:
    - echo "$COSIGN_PRIVATE_KEY" | cosign sign --key - $REGISTRY:$CI_COMMIT_SHA
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'

# Stage 6: Staging Deployment
deploy-staging:
  stage: deploy-staging
  <<: *kubectl_config
  environment:
    name: staging
    url: https://staging.example.com
  needs:
    - build-docker-image
  script:
    # Deploy using Helm
    - |
      helm upgrade --install app-staging ./helm-chart \
        --namespace staging \
        --create-namespace \
        --set image.tag=$CI_COMMIT_SHA \
        --set environment=staging \
        --set replicas=2 \
        --wait --timeout=600s

    # Wait for deployment
    - kubectl rollout status deployment/app-staging -n staging --timeout=600s

    # Run smoke tests
    - kubectl run smoke-test --rm -i --restart=Never --image=curlimages/curl:latest -- curl -f https://staging.example.com/health
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'

# Stage 7: Security Testing
dast-scan:
  stage: security-test
  include:
    - template: DAST.gitlab-ci.yml
  variables:
    DAST_WEBSITE: https://staging.example.com
    DAST_AUTH_URL: https://staging.example.com/login
  needs:
    - deploy-staging
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'

api-security-test:
  stage: security-test
  image: owasp/zap2docker-stable:latest
  needs:
    - deploy-staging
  script:
    - |
      zap-api-scan.py \
        -t https://staging.example.com/api/openapi.json \
        -f openapi \
        -J api-security-report.json
  artifacts:
    reports:
      dast: api-security-report.json
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'

load-testing:
  stage: security-test
  image: grafana/k6:latest
  needs:
    - deploy-staging
  script:
    - k6 run --out json=loadtest-results.json performance/load-test.js
  artifacts:
    paths:
      - loadtest-results.json
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'

# Stage 8: Production Deployment
deploy-production:
  stage: deploy-production
  <<: *kubectl_config
  environment:
    name: production
    url: https://example.com
  needs:
    - dast-scan
    - api-security-test
    - load-testing
  when: manual
  script:
    # Blue-Green deployment strategy
    - |
      # Deploy to green environment
      helm upgrade --install app-green ./helm-chart \
        --namespace production \
        --set image.tag=$CI_COMMIT_SHA \
        --set environment=production \
        --set slot=green \
        --set replicas=5 \
        --wait --timeout=600s

    # Health check green deployment
    - kubectl get pods -l app=app-green -n production
    - kubectl wait --for=condition=available deployment/app-green -n production --timeout=600s

    # Switch traffic (blue-green switch)
    - |
      kubectl patch service app-service -n production \
        --type='json' \
        -p='[{"op": "replace", "path": "/spec/selector/slot", "value": "green"}]'

    # Wait and verify
    - sleep 30
    - curl -f https://example.com/health

    # Scale down blue deployment
    - kubectl scale deployment app-blue --replicas=0 -n production
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'

# Stage 9: Monitoring
setup-monitoring:
  stage: monitor
  <<: *kubectl_config
  needs:
    - deploy-production
  script:
    # Deploy monitoring stack
    - kubectl apply -f monitoring/prometheus.yaml -n monitoring
    - kubectl apply -f monitoring/grafana.yaml -n monitoring
    - kubectl apply -f monitoring/alerts.yaml -n monitoring

    # Configure alerts for new deployment
    - |
      cat > alerting-config.yaml << EOF
      apiVersion: v1
      kind: ConfigMap
      metadata:
        name: prometheus-alerts
        namespace: monitoring
      data:
        alerts.yaml: |
          groups:
          - name: application
            rules:
            - alert: HighErrorRate
              expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
              for: 5m
              annotations:
                summary: "High error rate detected"
            - alert: HighLatency
              expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
              for: 5m
              annotations:
                summary: "High latency detected"
      EOF
    - kubectl apply -f alerting-config.yaml
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'

performance-monitoring:
  stage: monitor
  image: node:20-alpine
  needs:
    - deploy-production
  script:
    # Continuous performance monitoring
    - |
      cat > monitor.js << 'EOF'
      const https = require('https');

      async function checkHealth() {
        return new Promise((resolve, reject) => {
          const req = https.get('https://example.com/health', (res) => {
            const start = Date.now();
            res.on('data', () => {});
            res.on('end', () => {
              const latency = Date.now() - start;
              resolve({ status: res.statusCode, latency });
            });
          });
          req.on('error', reject);
          req.setTimeout(5000, () => reject(new Error('Timeout')));
        });
      }

      async function monitor() {
        for (let i = 0; i < 10; i++) {
          try {
            const result = await checkHealth();
            console.log(`Check ${i+1}: Status ${result.status}, Latency ${result.latency}ms`);

            if (result.status !== 200 || result.latency > 2000) {
              process.exit(1);
            }
          } catch (error) {
            console.error(`Check ${i+1}: Error - ${error.message}`);
            process.exit(1);
          }

          await new Promise(resolve => setTimeout(resolve, 30000)); // 30s interval
        }
      }

      monitor().then(() => console.log('Monitoring completed successfully'));
      EOF
    - node monitor.js
  timeout: 10 minutes
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'

# Global error handling
workflow_failure_notification:
  stage: monitor
  image: curlimages/curl:latest
  script:
    - |
      curl -X POST -H 'Content-type: application/json' \
        --data "{\"text\":\"❌ Pipeline failed for commit $CI_COMMIT_SHA in $CI_PROJECT_NAME\"}" \
        $SLACK_WEBHOOK_URL
  rules:
    - if: '$CI_PIPELINE_SOURCE == "push" && $CI_COMMIT_BRANCH == "main"'
      when: on_failure

# Cleanup
cleanup_resources:
  stage: monitor
  <<: *kubectl_config
  script:
    # Clean up old deployments
    - kubectl delete deployment -l version!=production -n production --ignore-not-found=true

    # Clean up old images
    - docker system prune -af --filter "until=168h" # 7 days

    # Clean up old artifacts
    - find /tmp -name "*.log" -mtime +7 -delete
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'
      when: always

# Daily security scan
nightly_security_scan:
  stage: validate
  <<: *docker_config
  script:
    - docker pull $REGISTRY:latest
    - docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest image --severity HIGH,CRITICAL $REGISTRY:latest
  rules:
    - if: '$CI_PIPELINE_SOURCE == "schedule"'

# Performance baseline
weekly_performance_baseline:
  stage: test
  image: grafana/k6:latest
  script:
    - k6 run --out json=baseline-results.json performance/baseline-test.js
  artifacts:
    expire_in: 30 days
    paths:
      - baseline-results.json
  rules:
    - if: '$CI_PIPELINE_SOURCE == "schedule" && $CI_PIPELINE_NAME == "weekly"'
```

### Jenkins Pipeline as Code
```groovy
// Advanced Jenkins Pipeline with comprehensive DevSecOps
pipeline {
    agent none

    // Global options
    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        disableConcurrentBuilds()
        timeout(time: 1, unit: 'HOURS')
        retry(3)
        timestamps()
    }

    // Environment variables
    environment {
        REGISTRY = 'ghcr.io'
        IMAGE_NAME = "${env.JOB_NAME}"
        NODE_VERSION = '20'
        DOCKER_BUILDKIT = '1'

        // Credentials
        GITHUB_TOKEN = credentials('github-token')
        DOCKER_CREDS = credentials('docker-registry')
        SONAR_TOKEN = credentials('sonarqube-token')
        SLACK_WEBHOOK = credentials('slack-webhook')

        // Feature flags
        SKIP_TESTS = params.SKIP_TESTS ?: false
        DEPLOY_ENV = params.DEPLOY_ENV ?: 'staging'
    }

    // Build parameters
    parameters {
        choice(
            name: 'DEPLOY_ENV',
            choices: ['staging', 'production'],
            description: 'Deployment environment'
        )
        booleanParam(
            name: 'SKIP_TESTS',
            defaultValue: false,
            description: 'Skip test execution'
        )
        booleanParam(
            name: 'FORCE_DEPLOY',
            defaultValue: false,
            description: 'Force deployment even if security checks fail'
        )
    }

    // Build triggers
    triggers {
        pollSCM('H/5 * * * *')  // Poll every 5 minutes
        cron('H 2 * * *')       // Nightly security scan
        upstream(upstreamProjects: 'shared-library', threshold: hudson.model.Result.SUCCESS)
    }

    stages {
        // Stage 1: Code Quality & Security Analysis
        stage('Code Analysis') {
            agent {
                docker {
                    image 'node:20-alpine'
                    args '-v /var/run/docker.sock:/var/run/docker.sock'
                }
            }

            steps {
                script {
                    // Checkout with credentials for private repos
                    checkout([
                        $class: 'GitSCM',
                        branches: [[name: '*/main']],
                        userRemoteConfigs: [[
                            url: 'https://github.com/company/repo.git',
                            credentialsId: 'github-token'
                        ]]
                    ])

                    // Install dependencies with caching
                    sh '''
                        npm ci --cache .npm --prefer-offline
                    '''

                    // Parallel code quality checks
                    parallel(
                        "ESLint": {
                            sh 'npm run lint -- --format=junit --output-file=eslint-results.xml'
                            publishTestResults testResultsPattern: 'eslint-results.xml'
                        },
                        "TypeScript": {
                            sh 'npm run type-check'
                        },
                        "Prettier": {
                            sh 'npm run format:check'
                        },
                        "Security Audit": {
                            sh '''
                                npm audit --audit-level moderate --json > audit-results.json || true
                                node scripts/parse-audit-results.js
                            '''
                        }
                    )
                }
            }

            post {
                always {
                    archiveArtifacts artifacts: 'audit-results.json', allowEmptyArchive: true
                    publishHTML([
                        allowMissing: false,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: 'reports',
                        reportFiles: 'code-quality.html',
                        reportName: 'Code Quality Report'
                    ])
                }
            }
        }

        // Stage 2: SAST Security Scanning
        stage('Security Scanning') {
            agent {
                docker {
                    image 'returntocorp/semgrep:latest'
                }
            }

            steps {
                script {
                    try {
                        // Semgrep security scanning
                        sh '''
                            semgrep --config=p/security-audit \
                                   --config=p/secrets \
                                   --config=p/owasp-top-ten \
                                   --json --output=semgrep-results.json .
                        '''

                        // Parse results and fail if critical issues found
                        def semgrepResults = readJSON file: 'semgrep-results.json'
                        def criticalIssues = semgrepResults.results.findAll {
                            it.extra?.severity == 'ERROR'
                        }

                        if (criticalIssues.size() > 0 && !params.FORCE_DEPLOY) {
                            error("Critical security issues found: ${criticalIssues.size()}")
                        }

                    } catch (Exception e) {
                        if (!params.FORCE_DEPLOY) {
                            throw e
                        }
                        echo "Security scan failed but continuing due to FORCE_DEPLOY"
                    }
                }
            }

            post {
                always {
                    archiveArtifacts artifacts: 'semgrep-results.json'
                    publishHTML([
                        allowMissing: true,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: '.',
                        reportFiles: 'semgrep-results.json',
                        reportName: 'Security Scan Results'
                    ])
                }
            }
        }

        // Stage 3: Build Application
        stage('Build') {
            agent {
                docker {
                    image 'node:20-alpine'
                }
            }

            environment {
                NODE_ENV = 'production'
            }

            steps {
                script {
                    // Build application
                    sh '''
                        npm ci --production
                        npm run build
                        npm run build:storybook
                    '''

                    // Generate build metadata
                    sh '''
                        echo "Build Info:" > build-info.txt
                        echo "Build Number: ${BUILD_NUMBER}" >> build-info.txt
                        echo "Git Commit: ${GIT_COMMIT}" >> build-info.txt
                        echo "Build Date: $(date)" >> build-info.txt
                        echo "Node Version: $(node --version)" >> build-info.txt
                    '''
                }
            }

            post {
                success {
                    archiveArtifacts artifacts: 'dist/**,build-info.txt', fingerprint: true
                    stash includes: 'dist/**,Dockerfile,docker-compose.yml', name: 'build-artifacts'
                }
            }
        }

        // Stage 4: Comprehensive Testing
        stage('Testing') {
            when {
                not { params.SKIP_TESTS }
            }

            parallel {
                stage('Unit Tests') {
                    agent {
                        docker {
                            image 'node:20-alpine'
                        }
                    }

                    steps {
                        sh '''
                            npm ci
                            npm run test:unit -- --coverage --ci --reporters=default --reporters=jest-junit
                        '''
                    }

                    post {
                        always {
                            publishTestResults testResultsPattern: 'junit.xml'
                            publishCoverage adapters: [
                                istanbulCoberturaAdapter('coverage/cobertura-coverage.xml')
                            ], sourceFileResolver: sourceFiles('STORE_LAST_BUILD')
                        }
                    }
                }

                stage('Integration Tests') {
                    agent {
                        docker {
                            image 'node:20-alpine'
                            args '--network host'
                        }
                    }

                    services {
                        postgres {
                            image 'postgres:15'
                            environment {
                                POSTGRES_DB = 'test_db'
                                POSTGRES_USER = 'postgres'
                                POSTGRES_PASSWORD = 'postgres'
                            }
                        }
                        redis {
                            image 'redis:7-alpine'
                        }
                    }

                    environment {
                        DATABASE_URL = 'postgres://postgres:postgres@localhost:5432/test_db'
                        REDIS_URL = 'redis://localhost:6379'
                    }

                    steps {
                        sh '''
                            npm ci
                            npm run db:migrate
                            npm run test:integration
                        '''
                    }

                    post {
                        always {
                            publishTestResults testResultsPattern: 'integration-test-results.xml'
                        }
                        failure {
                            archiveArtifacts artifacts: 'logs/**', allowEmptyArchive: true
                        }
                    }
                }

                stage('E2E Tests') {
                    agent {
                        docker {
                            image 'mcr.microsoft.com/playwright:v1.40.0-focal'
                        }
                    }

                    steps {
                        unstash 'build-artifacts'

                        sh '''
                            npm ci
                            npm run test:e2e:ci
                        '''
                    }

                    post {
                        always {
                            publishTestResults testResultsPattern: 'e2e-test-results.xml'
                        }
                        failure {
                            archiveArtifacts artifacts: 'playwright-report/**,test-results/**'
                        }
                    }
                }
            }
        }

        // Stage 5: Container Build & Scan
        stage('Container Build') {
            agent {
                docker {
                    image 'docker:20.10.16'
                    args '-v /var/run/docker.sock:/var/run/docker.sock'
                }
            }

            steps {
                unstash 'build-artifacts'

                script {
                    // Build multi-platform container
                    sh '''
                        docker buildx create --use --name multiarch || true
                        docker buildx build \
                            --platform linux/amd64,linux/arm64 \
                            --build-arg NODE_VERSION=${NODE_VERSION} \
                            --build-arg BUILD_NUMBER=${BUILD_NUMBER} \
                            --build-arg GIT_COMMIT=${GIT_COMMIT} \
                            --tag ${REGISTRY}/${IMAGE_NAME}:${GIT_COMMIT} \
                            --tag ${REGISTRY}/${IMAGE_NAME}:latest \
                            --push \
                            .
                    '''

                    // Container security scanning with Trivy
                    sh '''
                        docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
                            aquasec/trivy:latest image \
                            --format json \
                            --output trivy-results.json \
                            --severity HIGH,CRITICAL \
                            ${REGISTRY}/${IMAGE_NAME}:${GIT_COMMIT}
                    '''

                    // Parse Trivy results
                    def trivyResults = readJSON file: 'trivy-results.json'
                    def criticalVulns = trivyResults.Results?.findAll { result ->
                        result.Vulnerabilities?.any { vuln ->
                            vuln.Severity in ['HIGH', 'CRITICAL']
                        }
                    }

                    if (criticalVulns && !params.FORCE_DEPLOY) {
                        echo "Critical vulnerabilities found in container image"
                        currentBuild.result = 'UNSTABLE'
                    }
                }
            }

            post {
                always {
                    archiveArtifacts artifacts: 'trivy-results.json'
                }
            }
        }

        // Stage 6: Infrastructure as Code
        stage('Infrastructure') {
            when {
                branch 'main'
            }

            agent {
                docker {
                    image 'hashicorp/terraform:1.6.0'
                    args '--entrypoint="" -v /var/run/docker.sock:/var/run/docker.sock'
                }
            }

            environment {
                AWS_DEFAULT_REGION = 'us-west-2'
                TF_VAR_image_tag = "${env.GIT_COMMIT}"
                TF_VAR_environment = "${params.DEPLOY_ENV}"
            }

            steps {
                withCredentials([aws(credentialsId: 'aws-credentials')]) {
                    dir('infrastructure') {
                        script {
                            // Terraform operations
                            sh 'terraform init'
                            sh 'terraform plan -out=tfplan'

                            // Manual approval for production
                            if (params.DEPLOY_ENV == 'production') {
                                input message: 'Deploy to production?', ok: 'Deploy',
                                      submitterParameter: 'DEPLOYER'
                                echo "Deployment approved by: ${env.DEPLOYER}"
                            }

                            sh 'terraform apply tfplan'
                            sh 'terraform output -json > infrastructure-outputs.json'
                        }
                    }
                }
            }

            post {
                always {
                    archiveArtifacts artifacts: 'infrastructure/tfplan,infrastructure/infrastructure-outputs.json'
                }
            }
        }

        // Stage 7: Application Deployment
        stage('Deploy') {
            when {
                branch 'main'
            }

            agent {
                docker {
                    image 'bitnami/kubectl:1.28'
                }
            }

            steps {
                withCredentials([kubeconfigFile(credentialsId: 'kubeconfig')]) {
                    script {
                        // Blue-Green deployment
                        def currentSlot = sh(
                            script: "kubectl get service app-service -o jsonpath='{.spec.selector.slot}' || echo 'blue'",
                            returnStdout: true
                        ).trim()
                        def targetSlot = currentSlot == 'blue' ? 'green' : 'blue'

                        echo "Current slot: ${currentSlot}, Target slot: ${targetSlot}"

                        // Deploy to target slot
                        sh """
                            helm upgrade --install app-${targetSlot} ./helm-chart \\
                                --namespace ${params.DEPLOY_ENV} \\
                                --create-namespace \\
                                --set image.tag=${env.GIT_COMMIT} \\
                                --set environment=${params.DEPLOY_ENV} \\
                                --set slot=${targetSlot} \\
                                --set replicas=3 \\
                                --wait --timeout=600s
                        """

                        // Health check
                        sh "kubectl wait --for=condition=available deployment/app-${targetSlot} -n ${params.DEPLOY_ENV} --timeout=600s"

                        // Smoke test
                        def serviceUrl = sh(
                            script: "kubectl get ingress app-ingress -o jsonpath='{.spec.rules[0].host}'",
                            returnStdout: true
                        ).trim()

                        sh "curl -f https://${serviceUrl}/health"

                        // Switch traffic
                        sh """
                            kubectl patch service app-service -n ${params.DEPLOY_ENV} \\
                                --type='json' \\
                                -p='[{"op": "replace", "path": "/spec/selector/slot", "value": "${targetSlot}"}]'
                        """

                        // Verify switch
                        sleep 30
                        sh "curl -f https://${serviceUrl}/health"

                        // Scale down old deployment
                        sh "kubectl scale deployment app-${currentSlot} --replicas=0 -n ${params.DEPLOY_ENV}"
                    }
                }
            }

            post {
                success {
                    script {
                        env.DEPLOYMENT_SUCCESS = 'true'
                        env.DEPLOYED_VERSION = env.GIT_COMMIT
                    }
                }
                failure {
                    script {
                        // Automatic rollback on failure
                        sh """
                            kubectl rollout undo deployment/app-${targetSlot} -n ${params.DEPLOY_ENV}
                            kubectl patch service app-service -n ${params.DEPLOY_ENV} \\
                                --type='json' \\
                                -p='[{"op": "replace", "path": "/spec/selector/slot", "value": "${currentSlot}"}]'
                        """
                    }
                }
            }
        }

        // Stage 8: Post-Deployment Testing
        stage('Post-Deployment') {
            when {
                allOf {
                    branch 'main'
                    environment name: 'DEPLOYMENT_SUCCESS', value: 'true'
                }
            }

            parallel {
                stage('Security Testing') {
                    agent {
                        docker {
                            image 'owasp/zap2docker-stable:latest'
                            args '--network host'
                        }
                    }

                    steps {
                        script {
                            def targetUrl = "https://${params.DEPLOY_ENV}.example.com"

                            // DAST scanning
                            sh """
                                zap-baseline.py -t ${targetUrl} \\
                                    -J dast-results.json \\
                                    -r dast-report.html
                            """
                        }
                    }

                    post {
                        always {
                            archiveArtifacts artifacts: 'dast-results.json,dast-report.html'
                        }
                    }
                }

                stage('Performance Testing') {
                    agent {
                        docker {
                            image 'grafana/k6:latest'
                        }
                    }

                    steps {
                        script {
                            sh '''
                                k6 run --out json=performance-results.json \\
                                    performance/load-test.js
                            '''

                            // Parse performance results
                            def perfResults = readJSON file: 'performance-results.json'
                            // Add performance validation logic here
                        }
                    }

                    post {
                        always {
                            archiveArtifacts artifacts: 'performance-results.json'
                        }
                    }
                }
            }
        }

        // Stage 9: Monitoring Setup
        stage('Monitoring') {
            when {
                allOf {
                    branch 'main'
                    environment name: 'DEPLOYMENT_SUCCESS', value: 'true'
                }
            }

            agent {
                docker {
                    image 'bitnami/kubectl:1.28'
                }
            }

            steps {
                withCredentials([kubeconfigFile(credentialsId: 'kubeconfig')]) {
                    sh '''
                        # Deploy monitoring resources
                        kubectl apply -f monitoring/servicemonitor.yaml -n monitoring
                        kubectl apply -f monitoring/alerts.yaml -n monitoring

                        # Update Grafana dashboards
                        kubectl create configmap grafana-dashboard-app \\
                            --from-file=monitoring/dashboard.json \\
                            -n monitoring \\
                            --dry-run=client -o yaml | kubectl apply -f -
                    '''
                }
            }
        }
    }

    post {
        always {
            script {
                // Collect all artifacts
                def buildArtifacts = [
                    "Build Number: ${env.BUILD_NUMBER}",
                    "Git Commit: ${env.GIT_COMMIT}",
                    "Deployed Version: ${env.DEPLOYED_VERSION ?: 'N/A'}",
                    "Environment: ${params.DEPLOY_ENV}",
                    "Build Result: ${currentBuild.currentResult}"
                ].join('\n')

                writeFile file: 'build-summary.txt', text: buildArtifacts
                archiveArtifacts artifacts: 'build-summary.txt'
            }
        }

        success {
            script {
                // Send success notification
                def slackMessage = [
                    channel: '#deployments',
                    color: 'good',
                    message: """
                        ✅ Deployment successful!
                        Environment: ${params.DEPLOY_ENV}
                        Version: ${env.GIT_COMMIT}
                        Build: ${env.BUILD_URL}
                    """.stripIndent()
                ]

                httpRequest(
                    httpMode: 'POST',
                    contentType: 'APPLICATION_JSON',
                    url: env.SLACK_WEBHOOK,
                    requestBody: groovy.json.JsonBuilder(slackMessage).toString()
                )
            }
        }

        failure {
            script {
                // Send failure notification with details
                def failureStage = currentBuild.rawBuild.getAction(jenkins.model.InterruptedBuildAction.class)?.getCauses()[0]?.getShortDescription() ?: 'Unknown'

                def slackMessage = [
                    channel: '#deployments',
                    color: 'danger',
                    message: """
                        ❌ Deployment failed!
                        Environment: ${params.DEPLOY_ENV}
                        Stage: ${failureStage}
                        Build: ${env.BUILD_URL}
                        Logs: ${env.BUILD_URL}console
                    """.stripIndent()
                ]

                httpRequest(
                    httpMode: 'POST',
                    contentType: 'APPLICATION_JSON',
                    url: env.SLACK_WEBHOOK,
                    requestBody: groovy.json.JsonBuilder(slackMessage).toString()
                )

                // Auto-rollback for production
                if (params.DEPLOY_ENV == 'production' && env.DEPLOYMENT_SUCCESS) {
                    node('kubectl') {
                        sh 'kubectl rollout undo deployment/app-production -n production'
                    }
                }
            }
        }

        unstable {
            script {
                def slackMessage = [
                    channel: '#deployments',
                    color: 'warning',
                    message: """
                        ⚠️ Deployment completed with warnings
                        Environment: ${params.DEPLOY_ENV}
                        Build: ${env.BUILD_URL}
                    """.stripIndent()
                ]

                httpRequest(
                    httpMode: 'POST',
                    contentType: 'APPLICATION_JSON',
                    url: env.SLACK_WEBHOOK,
                    requestBody: groovy.json.JsonBuilder(slackMessage).toString()
                )
            }
        }

        cleanup {
            // Cleanup workspace and temporary resources
            cleanWs()

            // Clean up Docker images older than 7 days
            sh 'docker image prune -af --filter "until=168h" || true'
        }
    }
}
```

## Skill Activation Triggers

This skill automatically activates when:
- CI/CD pipeline setup is needed
- DevOps automation is requested
- Deployment strategy planning is required
- Pipeline optimization is needed
- DevSecOps integration is requested
- Infrastructure automation is required

This comprehensive CI/CD pipelines skill provides expert-level capabilities for building, securing, and optimizing modern deployment pipelines across all major platforms using cutting-edge tools and methodologies.