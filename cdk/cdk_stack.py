import aws_cdk.core as cdk
import aws_cdk.aws_apigateway as agw
import aws_cdk.aws_events as events
import aws_cdk.aws_events_targets as eventsTargets
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_iam as iam
import aws_cdk.aws_stepfunctions as sfn
import aws_cdk.aws_stepfunctions_tasks as tasks
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_s3 as s3
import subprocess
import requests

class CdkStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)


        codeLocation = 'lambdas'
        layerLocation = self.installRequirements(codeLocation)
        self.ip = requests.get('https://api.ipify.org').text
        self.vpc = ec2.Vpc.from_lookup(self, 'defaultVpc',
            is_default=True
        )
        self.lambdaRole = self.createLambdaRole()
        self.lambdaCode = lambda_.Code.from_asset(codeLocation)
        self.lambdaLayer = lambda_.LayerVersion(self, 'lambdaLayer', 
            code=lambda_.Code.from_asset(layerLocation),
            compatible_runtimes=[
                lambda_.Runtime.PYTHON_3_8
            ]
        )
        self.statesRole = iam.Role(self, 'statesExecutionRole',
            assumed_by=iam.ServicePrincipal('states.amazonaws.com'),
            inline_policies={
                'StatesExecutionPolicy': iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=['lambda:InvokeFunction'],
                            resources=['*']
                        )
                    ]
                )
            }
        )

        api = agw.RestApi(self, 'lntipbot',
            endpoint_types=[agw.EndpointType.REGIONAL],
            deploy_options=agw.StageOptions(
                metrics_enabled=True
            )
        )

        api.root.add_resource('info', default_integration=agw.MockIntegration(
            integration_responses=[
                agw.IntegrationResponse(
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
        )).add_method('GET',
            method_responses=[{
                'statusCode': '301',
                'responseParameters': {
                    'method.response.header.Location': True,
                    'method.response.header.Cache-Control': True
                }
            }]
        )

        api.root.add_resource('uri', default_integration=agw.LambdaIntegration(
            self.createLambda('invoiceUriFunction', 'getURI.getURI')
        )).add_method('GET')

        api.root.add_resource('qr', default_integration=agw.LambdaIntegration(
            self.createLambda('qrFunction', 'qrEncoder.qrEncoder')
        )).add_method('GET')

        events.Rule(self, 'oauthRefreshEvent',
            schedule=events.Schedule.rate(cdk.Duration.minutes(28)),
            targets=[eventsTargets.LambdaFunction(
                self.createLambda('oauthFunction', 'redditOAuthRequester.redditOAuthRequester')
            )]
        )

        self.settledInvoiceHandler = self.createLambda('settledInvoiceHandler', 'settledInvoiceHandler.settledInvoiceHandler')

        self.createLambda('apiTest', 'lambda_function.lambda_handler')
        
        withdrawWorkflow = self.createWithdrawWorkflow()
        tipWorkflow = self.createTipWorkflow()
        
        events.Rule(self, 'redditCommentScannerEvent',
            schedule=events.Schedule.rate(cdk.Duration.minutes(1)),
            targets=[eventsTargets.LambdaFunction(
                lambda_.Function(self, 'redditCommentScanner', 
                    code=self.lambdaCode,
                    runtime=lambda_.Runtime.PYTHON_3_8,
                    handler='scanComments.scannerLoop',
                    role=self.lambdaRole,
                    layers=[self.lambdaLayer],
                    timeout=cdk.Duration.seconds(55),
                    reserved_concurrent_executions=1
                ),
                event=events.RuleTargetInput.from_object({
                    'tipWorkflowArn': tipWorkflow.state_machine_arn,
                    'withdrawWorkflowArn': withdrawWorkflow.state_machine_arn
                })
            )]
        )

        self.backupBucket = s3.Bucket(self, 'bitcoindBackups',
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            bucket_name='bitcoind-pruned-backups-lntipbot',
        )

        serverRole = self.createServerRole()
        
        volume = ec2.Volume(self, 'serverVolume',
            removal_policy=cdk.RemovalPolicy.RETAIN,
            volume_type=ec2.EbsDeviceVolumeType.GP3,
            availability_zone='us-west-2d',
            snapshot_id='snap-0f81f825ae3251a39',
            size=cdk.Size.gibibytes(16),
        )
        securityGroup = ec2.SecurityGroup(self, 'serverSecurityGroup',
            vpc=self.vpc,
            description='Server Security Group',
        )
        securityGroup.add_ingress_rule(
            peer=ec2.Peer.ipv4(cidr_ip=f'{self.ip}/32'),
            connection=ec2.Port.tcp(22),
            description='Allow specific host for ssh'
        )
        securityGroup.add_egress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.all_traffic(),
            description='Allow all outbound'
        )
        securityGroup.apply_removal_policy(cdk.RemovalPolicy.RETAIN)

        instance = ec2.Instance(self, 'serverInstance',
            instance_type=ec2.InstanceType('t3a.small'),
            vpc=self.vpc,
            machine_image=ec2.MachineImage.generic_linux({
                'us-west-2': 'ami-03d5c68bab01f3496'
            }),
            role=serverRole,
            security_group=securityGroup,
            availability_zone='us-west-2d',
        )
        
        instance.apply_removal_policy(cdk.RemovalPolicy.RETAIN)

        instance.node.default_child.volumes = [
            ec2.CfnInstance.VolumeProperty(
                device='/dev/sda1',
                volume_id=volume.volume_id,
            )
        ]

        # eip = ec2.CfnEIP(self, 'serverEIP',
        #     domain='vpc',
        #     instance_id=instance.instance_id,
        # )
        
        # networkInterface = ec2.CfnInstance.NetworkInterfaceProperty(
        #     subnet_id=self.vpc.select_subnets(
        #         availability_zones=['us-west-2d']
        #     ).subnet_ids[0],
        #     private_ip_address='172.31.59.110',
        #     group_set=[
        #         securityGroup.security_group_id,
        #     ],
        #     delete_on_termination=False,
        #     device_index='1',
        # )

        # instance.node.default_child.network_interfaces = [
        #     networkInterface
        # ]


    def createLambda(self, functionName, handlerName):
        return lambda_.Function(self, functionName, 
            code=self.lambdaCode,
            runtime=lambda_.Runtime.PYTHON_3_8,
            handler=handlerName,
            role=self.lambdaRole,
            layers=[self.lambdaLayer],
            timeout=cdk.Duration.seconds(10)
        )

    def createWithdrawWorkflow(self):
        payInvoiceFailed = tasks.LambdaInvoke(self, 'payInvoiceFailed',
            lambda_function=self.createLambda('payInvoiceFailedLambda', 'payInvoiceFailed.payInvoiceFailed'),
            timeout=cdk.Duration.seconds(300)
        ).next(sfn.Fail(self, 'tipErrorState'))

        payInvoiceSucceeded = tasks.LambdaInvoke(self, 'payInvoiceSucceeded', 
            lambda_function=self.createLambda('payInvoiceSucceededLambda', 'payInvoiceSucceeded.payInvoiceSucceeded'),
            timeout=cdk.Duration.seconds(300)
        ).next(sfn.Succeed(self, 'tipSuccessState'))

        self.payInvoice = tasks.StepFunctionsInvokeActivity(self, 'payInvoice',
            activity=sfn.Activity(self, 'payInvoiceActivity'),
            heartbeat=cdk.Duration.seconds(86400),
            timeout=cdk.Duration.seconds(86400),
        )
        self.payInvoice.add_retry(
            backoff_rate=2,
            errors=['States.Timeout'],
            interval=cdk.Duration.seconds(600),
            max_attempts=0
        )
        self.payInvoice.add_catch(
            handler=payInvoiceFailed,
            errors=['States.ALL'],
            result_path='$.errorInfo'
        )
        self.payInvoice.next(payInvoiceSucceeded)

        return sfn.StateMachine(self, 'withdrawWorkflow',
            definition=self.payInvoice,
            role=self.statesRole
        )

    def createTipWorkflow(self):
        notifyTipper = tasks.LambdaInvoke(self, 'notifyTipper',
            lambda_function=self.createLambda('notifyTipperLambda', 'tipNotifier.tipNotifier'),
            timeout=cdk.Duration.seconds(300)
        ).next(sfn.Succeed(self, 'withdrawSuccessState'))

        self.getTipperInvoice = tasks.StepFunctionsInvokeActivity(self, 'getTipperInvoice',
            activity=sfn.Activity(self, 'getTipperInvoiceActivity'),
            heartbeat=cdk.Duration.seconds(60),
            timeout=cdk.Duration.seconds(86400),
        )
        self.getTipperInvoice.add_retry(
            backoff_rate=1.5,
            errors=['States.Timeout'],
            interval=cdk.Duration.seconds(60),
            max_attempts=7
        )
        self.getTipperInvoice.add_catch(
            handler=sfn.Fail(self, 'withdrawErrorState'),
            errors=['States.ALL'],
            result_path='$.errorInfo'
        )
        self.getTipperInvoice.next(notifyTipper)

        return sfn.StateMachine(self, 'tipWorkflow',
            definition=self.getTipperInvoice,
            role=self.statesRole
        )

    def installRequirements(self, path):
        outPath = f'{path}_deps'
        subprocess.check_call(f'pip install --upgrade -r {path}/requirements.txt -t {outPath}/python'.split())
        
        # pip includes __pycache__ which includes .pyc files that differ for every pip install 
        # that intereferes with cdk's code checksums causing unchanged assets to deploy every time
        subprocess.check_call(f'pyclean {outPath}'.split())

        return outPath

    def createServerRole(self):
        return iam.Role(self, 'serverRole',
            assumed_by=iam.ServicePrincipal('ec2.amazonaws.com'),
            inline_policies={
                'LNServerPolicy': iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                'lambda:InvokeFunction',
                            ],
                            resources=[
                                self.settledInvoiceHandler.function_arn
                            ]
                            # TODO: Add conditions on IP?
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                's3:GetObject',
                                's3:PutObject',
                                's3:PutObjectAcl'
                            ],
                            resources=[
                                f'{self.backupBucket.bucket_arn}/*'
                            ]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                'states:GetActivityTask',
                                'states:SendTaskSuccess',
                                'states:SendTaskFailure',
                                'states:SendTaskHeartbeat',
                            ],
                            resources=[
                                # I gave up on trying to get an ARN from the StepFunctionsInvokeActivity resources.  ARN retrieval in cdk is
                                # a nightmare if the resource does not have a convenient helper like function_arn above
                                '*'
                            ]
                        ),
                    ]
                )
            }
        )

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
                'StatesPolicy': iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=['states:StartExecution'],
                            resources=['*']
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
