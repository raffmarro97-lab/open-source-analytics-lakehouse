
pipeline {
    agent {
        label 'lakehouse'
    }

    options {
        skipDefaultCheckout(true)
        timestamps()
    }
 
    parameters {
        booleanParam(
            name: 'DEPLOY_DEV',
            defaultValue: false,
            description: 'Deploy Databricks Asset Bundle to DEV'
        )
        
        booleanParam(
            name: 'RUN_DEV',
            defaultValue: false,
            description: 'Execute Databricks Job in DEV after deployment'
        )
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Verify Repository') {
            steps {
                sh '''
                    set -eu

                    echo "Checking repository..."
                    git rev-parse --short HEAD

                    test -f databricks.yml
                    test -f resources/github_analytics.job.yml
                    test -f terraform/main.tf
                    test -f terraform/backend.tf

                    echo "Repository verification successful!"
                '''
            }
        }

        stage('Verify CI Tools') {
            steps {
                sh '''
                    echo "Checking Terraform..."
                    terraform version

                    echo "Checking Databricks CLI..."
                    databricks version

                    echo "Checking Git..."
                    git --version
                '''
            }
        }

        stage('PySpark Unit Tests') {
            steps {

                sh '''
                    set -eu
                    echo "Running PySpark unit tests..."
                    python3 -m pytest -v tests/
                '''
        }

        stage('Terraform Format') {
            steps {
                sh '''
                    terraform -chdir=terraform fmt -check -recursive
                '''
            }
        }

        stage('Terraform Validate') {
            steps {
                sh '''
                    terraform -chdir=terraform validate -no-color
                '''
            }
        }

        stage('Terraform Remote State') {
            steps {
                withCredentials([
                    string(
                        credentialsId: 'gitlab-terraform-state-token',
                        variable: 'TF_HTTP_PASSWORD'
                    )
                ]) {
                    withEnv([
                        'TF_HTTP_USERNAME=raffmarro97',
                        'TF_HTTP_ADDRESS=https://gitlab.com/api/v4/projects/88900594/terraform/state/github-analytics-infra-dev',
                        'TF_HTTP_LOCK_METHOD=POST',
                        'TF_HTTP_UNLOCK_METHOD=DELETE'
                    ]) {
                        sh '''
                            set -eu

                            export TF_HTTP_LOCK_ADDRESS="${TF_HTTP_ADDRESS}/lock"
                            export TF_HTTP_UNLOCK_ADDRESS="${TF_HTTP_ADDRESS}/lock"

                            echo "Initializing GitLab remote backend..."

                            terraform -chdir=terraform init -reconfigure -lockfile=readonly -input=false -no-color

                            echo "Reading Terraform remote state..."

                            terraform -chdir=terraform state list
                        '''
                    }
                }
            }
        }

        stage('Terraform Plan') {
            steps {
                withCredentials([
                    string(
                        credentialsId: 'gitlab-terraform-state-token',
                        variable: 'TF_HTTP_PASSWORD'
                    ),
                    string(
                        credentialsId: 'databricks-ci-token',
                        variable: 'DATABRICKS_TOKEN'
                    )
                ]) {
                    withEnv([
                        'DATABRICKS_HOST=https://dbc-ffab9e1e-aa5d.cloud.databricks.com',
                        'TF_HTTP_USERNAME=raffmarro97',
                        'TF_HTTP_ADDRESS=https://gitlab.com/api/v4/projects/88900594/terraform/state/github-analytics-infra-dev',
                        'TF_HTTP_LOCK_METHOD=POST',
                        'TF_HTTP_UNLOCK_METHOD=DELETE'
                    ]) {
                        sh '''
                            set +x
                            set -eu

                            export TF_HTTP_LOCK_ADDRESS="${TF_HTTP_ADDRESS}/lock"
                            export TF_HTTP_UNLOCK_ADDRESS="${TF_HTTP_ADDRESS}/lock"

                            terraform -chdir=terraform init \
                                -reconfigure \
                                -lockfile=readonly \
                                -input=false \
                                -no-color

                            terraform -chdir=terraform plan \
                                -input=false \
                                -no-color
                        '''
                    }
                }
            }
        }

        stage('Databricks Bundle Validate') {
            steps {
                withCredentials([
                    string(
                        credentialsId: 'databricks-ci-token',
                        variable: 'DATABRICKS_TOKEN'
                    )
                ]) {
                    withEnv([
                        'DATABRICKS_HOST=https://dbc-ffab9e1e-aa5d.cloud.databricks.com',
                        'DATABRICKS_AUTH_TYPE=pat'
                    ]) {
                        sh '''
                            set -eu

                            for target in dev staging prod; do
                                echo "Validating Databricks Bundle: $target"

                                databricks bundle validate -t "$target"

                                echo "Validation successful: $target"
                            done
                        '''
                    }
                }
            }
        }

        stage('Deploy Databricks DEV') {
            when {
                expression { params.DEPLOY_DEV == true }
            }

            steps {
                withCredentials([
                    string(
                        credentialsId: 'databricks-ci-token',
                        variable: 'DATABRICKS_TOKEN'
                    )
                ]) {
                    withEnv([
                        'DATABRICKS_HOST=https://dbc-ffab9e1e-aa5d.cloud.databricks.com',
                        'DATABRICKS_AUTH_TYPE=pat'
                    ]) {
                        sh '''
                            set -eu

                            echo "Deploying Databricks Bundle to DEV..."

                            databricks bundle deploy -t dev

                            echo "DEV deployment completed!"
                        '''
                    }
                }
            }
        }

        stage('Run Databricks DEV') {
            when {
                allOf {
                    expression { params.DEPLOY_DEV == true }
                    expression { params.RUN_DEV == true }
                }
            }

            steps {
                withCredentials([
                    string(
                        credentialsId: 'databricks-ci-token',
                        variable: 'DATABRICKS_TOKEN'
                    )
                ]) {
                    withEnv([
                        'DATABRICKS_HOST=https://dbc-ffab9e1e-aa5d.cloud.databricks.com',
                        'DATABRICKS_AUTH_TYPE=pat'
                    ]) {
                        sh '''
                            set -eu

                            echo "Running Databricks Job in DEV..."

                            databricks bundle run -t dev github_analytics_pipeline

                            echo "DEV Job execution completed!"
                        '''
                    }
                }
            }
        }
        

}

    }

    post {
        success {
            echo 'Jenkins pipeline completed successfully!'
        }
        failure {
            echo 'Jenkins pipeline failed!'
        }
    }
}
