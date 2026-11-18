
pipeline {
    agent {
        label 'lakehouse'
    }

    options {
        skipDefaultCheckout(true)
        timestamps()
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
