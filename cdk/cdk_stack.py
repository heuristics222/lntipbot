from aws_cdk import core as cdk
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as eventsTargets
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_iam as iam
import pyclean
import subprocess

class CdkStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)


        codeLocation = 'lambdas'
        layerLocation = self.installRequirements(codeLocation)
        self.lambdaRole = self.createLambdaRole()
        self.lambdaCode = lambda_.Code.from_asset(codeLocation)
        self.lambdaLayer = lambda_.LayerVersion(self, 'lambdaLayer', 
            code=lambda_.Code.from_asset(layerLocation),
            compatible_runtimes=[
                lambda_.Runtime.PYTHON_3_8
            ]
        )

        api = apigateway.RestApi(self, 'lntipbot',
            endpoint_types=[apigateway.EndpointType.REGIONAL],
            deploy_options=apigateway.StageOptions(
                metrics_enabled=True
            )
        )

        info = api.root.add_resource('info', default_integration=apigateway.MockIntegration(
            integration_responses=[
                apigateway.IntegrationResponse(
                    status_code='301',
                    response_parameters={
                        'method.response.header.Location': '\'https://www.reddit.com/r/LNTipBot2/wiki/index\'',
                        'method.response.header.Cache-Control': '\'max-age=300\''
                    }
                )
            ],
            request_templates={
                'application/json': '{"statusCode": 301}'
            }
        ))

        info.add_method('GET',
            method_responses=[{
                'statusCode': '301',
                'responseParameters': {
                    'method.response.header.Location': True,
                    'method.response.header.Cache-Control': True
                }
            }]
        )

        invoiceUri = api.root.add_resource('uri', default_integration=apigateway.LambdaIntegration(
            self.createLambda('invoiceUriFunction', 'getURI.getURI')
        ))

        invoiceUri.add_method('GET')

        qrUri = api.root.add_resource('qr', default_integration=apigateway.LambdaIntegration(
            self.createLambda('qrFunction', 'qrEncoder.qrEncoder')
        ))

        qrUri.add_method('GET')

        
        oauthFunction = self.createLambda('oauthFunction', 'redditOAuthRequester.redditOAuthRequester')
        rule = events.Rule(self, 'oauthRefreshEvent',
            schedule=events.Schedule.rate(cdk.Duration.minutes(28)),
            targets=[eventsTargets.LambdaFunction(oauthFunction)]
        )

        

    def createLambda(self, functionName, handlerName):
        return lambda_.Function(self, functionName,
            code=self.lambdaCode,
            runtime=lambda_.Runtime.PYTHON_3_8,
            handler=handlerName,
            role=self.lambdaRole,
            layers=[self.lambdaLayer],
            timeout=cdk.Duration.seconds(10)
        )

    def installRequirements(self, path):
        outPath = f'{path}_deps'
        subprocess.check_call(f'pip install --upgrade -r {path}/requirements.txt -t {outPath}/python'.split())
        
        # pip includes __pycache__ which includes .pyc files that differ for every pip install 
        # that intereferes with cdk's code checksums causing unchanged assets to deploy every time
        subprocess.check_call(f'pyclean {outPath}'.split())

        return outPath

    def createLambdaRole(self):
        return iam.Role(self, 'lambdaRole',
            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),
            inline_policies={
                'DdbPolicy': iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                'dynamodb:PutItem',
                                'dynamodb:GetItem',
                                'dynamodb:UpdateItem'
                            ],
                            resources=[
                                # TODO: import to cdk
                                'arn:aws:dynamodb:us-west-2:434623153115:table/Balance',
                                'arn:aws:dynamodb:us-west-2:434623153115:table/Data',
                                'arn:aws:dynamodb:us-west-2:434623153115:table/Tips'
                            ]
                        )
                    ]
                ),
                'LogPolicy': iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                'logs:CreateLogGroup',
                                'logs:CreateLogStream',
                                'logs:PutLogEvents'
                            ],
                            resources=[
                                'arn:aws:logs:*:*:*'
                            ]
                        )
                    ]
                )
            }
        )
