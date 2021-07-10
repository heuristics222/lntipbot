from aws_cdk import core as cdk
from aws_cdk import aws_apigateway as apigateway

class CdkStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        api = apigateway.RestApi(self, "lntipbot")

        info = api.root.add_resource("info", default_integration=apigateway.MockIntegration(
            integration_responses=[
                apigateway.IntegrationResponse(
                    status_code='301',
                    response_parameters={
                        'method.response.header.Location': "'https://www.reddit.com/r/LNTipBot2/wiki/index'",
                        'method.response.header.Cache-Control': "'max-age=300'"
                    }
                )
            ],
            request_templates={
                'application/json': '{"statusCode": 301}'
            }
        ))

        info.add_method("GET",
            method_responses=[{
                'statusCode': '301',
                'responseParameters': {
                    'method.response.header.Location': True,
                    'method.response.header.Cache-Control': True
                }
            }]
        )
