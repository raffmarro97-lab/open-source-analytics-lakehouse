
# Jenkins inbound agent with Java 21
FROM jenkins/inbound-agent:jdk21

USER root

# Install required utilities
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    unzip \
    git \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install Terraform CLI
ARG TERRAFORM_VERSION=1.17.1

RUN curl -fsSL \
    -o /tmp/terraform.zip \
    "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" && \
    unzip -q /tmp/terraform.zip -d /usr/local/bin && \
    rm /tmp/terraform.zip

# Install Databricks CLI
RUN curl -fsSL \
    https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh \
    -o /tmp/install-databricks.sh && \
    sh /tmp/install-databricks.sh && \
    rm /tmp/install-databricks.sh

# Run agent as non-root user
USER jenkins
