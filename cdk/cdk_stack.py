from aws_cdk import aws_apigateway as agw
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_cloudwatch_actions as cwa
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as eventsTargets
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as snss
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from aws_cdk import custom_resources as cr
from aws_cdk import Duration, Fn, RemovalPolicy, Size, Stack
from constructs import Construct
import hashlib
import json
import os
import requests
import subprocess
import typing

class CdkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)


        codeLocation = 'lambdas'
        layerLocation = self.installRequirements(codeLocation)
        self.ip = self.getIp()
        self.vpc = self.createVpc()
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
                        'method.response.header.Location': '\'https://www.reddit.com/r/lntipbot/wiki/index\'',
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
            schedule=events.Schedule.rate(Duration.minutes(28)),
            targets=[eventsTargets.LambdaFunction(
                self.createLambda('oauthFunction', 'redditOAuthRequester.redditOAuthRequester')
            )]
        )

        self.settledInvoiceHandler = self.createLambda('settledInvoiceHandler', 'settledInvoiceHandler.settledInvoiceHandler')

        self.createLambda('apiTest', 'lambda_function.lambda_handler')

        withdrawWorkflow = self.createWithdrawWorkflow()
        tipWorkflow = self.createTipWorkflow()

        events.Rule(self, 'redditCommentScannerEvent',
            schedule=events.Schedule.rate(Duration.minutes(1)),
            targets=[eventsTargets.LambdaFunction(
                lambda_.Function(self, 'redditCommentScanner',
                    code=self.lambdaCode,
                    runtime=lambda_.Runtime.PYTHON_3_8,
                    handler='scanComments.scannerLoop',
                    role=self.lambdaRole,
                    layers=[self.lambdaLayer],
                    timeout=Duration.seconds(55),
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

        self.serverRole = self.createServerRole()
        self.securityGroup = self.createSecurityGroup()
        self.createServer()

        self.createOps()

        self.createWikiResources()

    def createWikiResources(self):
        wikiUpdater = self.createLambda('wikiUpdater', 'updateWiki.updateWiki')

        wikiPath = 'lambdas/resources/wiki'

        for subreddit in os.listdir(wikiPath):
            subredditPath = wikiPath + '/' + subreddit

            for page in os.listdir(subredditPath):
                pagePath = subredditPath + '/' + page
                id = (subreddit + '/' + page).replace('/', '_')

                if not page.endswith('.md'):
                    continue
                pageName = page[0:-3]

                with open(pagePath, 'rb') as file:
                    fileContent = file.read()

                    call = cr.AwsSdkCall(
                        service='Lambda',
                        action='invoke',
                        physical_resource_id=cr.PhysicalResourceId.of(id),
                        parameters={
                            'FunctionName': wikiUpdater.function_name,
                            'InvocationType': 'RequestResponse',
                            'Payload': json.dumps({
                                'subreddit': subreddit,
                                'page': pageName,
                                'dedupId': hashlib.md5(fileContent).hexdigest()
                            })
                        }
                    )
                    acr = cr.AwsCustomResource(self, id,
                        on_create=call,
                        on_update=call,
                        install_latest_aws_sdk=False,
                        policy=cr.AwsCustomResourcePolicy.from_statements([
                            iam.PolicyStatement(
                                actions=[
                                    "lambda:InvokeFunction"
                                ],
                                effect=iam.Effect.ALLOW,
                                resources=[
                                    wikiUpdater.function_arn
                                ]
                            )
                        ])
                    )
                    acr.node.add_dependency(wikiUpdater)


    def getEmail(self):
        if not os.path.exists('.tipbotconfiguration.json'):
            with open('.tipbotconfiguration.json', 'w') as f:
                json.dump({'email':''}, f)

        with open('.tipbotconfiguration.json', 'r') as f:
            email = json.load(f)['email']
            if email == '':
                raise Exception('No email found, enter email for alarm notification in a file called .tipbotconfiguration.json')
            return email

    def createOps(self):
        alarmTopic = sns.Topic(self, 'TipBotAlarmTopic',
            display_name='TipBotAlarmTopic',
            fifo=False,
        )
        alarmTopic.add_subscription(snss.EmailSubscription(self.getEmail(), json=True))

        cw.CompositeAlarm(self, 'TipBotCompositeAlarm',
            alarm_rule=cw.AlarmRule.any_of(
                cw.Alarm(self, "LNDAlarm",
                    metric=cw.Metric(
                        metric_name='LndUp',
                        namespace='LNTipBot',
                        period=Duration.minutes(1),
                        statistic='sum',
                        unit=cw.Unit.NONE,
                    ),
                    threshold=1,
                    actions_enabled=False,
                    alarm_description='Alarm for when the LND service has gone down',
                    alarm_name='LND Alarm',
                    comparison_operator=cw.ComparisonOperator.LESS_THAN_THRESHOLD,
                    datapoints_to_alarm=5,
                    evaluation_periods=5,
                    treat_missing_data=cw.TreatMissingData.BREACHING
                ),
                cw.Alarm(self, "BTCAlarm",
                    metric=cw.Metric(
                        metric_name='BtcUp',
                        namespace='LNTipBot',
                        period=Duration.minutes(1),
                        statistic='sum',
                        unit=cw.Unit.NONE,
                    ),
                    threshold=1,
                    actions_enabled=False,
                    alarm_description='Alarm for when the BTC service has gone down',
                    alarm_name='BTC Alarm',
                    comparison_operator=cw.ComparisonOperator.LESS_THAN_THRESHOLD,
                    datapoints_to_alarm=5,
                    evaluation_periods=5,
                    treat_missing_data=cw.TreatMissingData.BREACHING
                )
            ),
            actions_enabled=True,
            alarm_description='TipBot Composite Alarm',
            composite_alarm_name='TipBot Composite Alarm',
        ).add_alarm_action(cwa.SnsAction(alarmTopic))

    def createVpc(self):
        vpc = ec2.Vpc(self, 'serverVpc',
            cidr='10.0.0.0/16',
            max_azs=1,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name='serverSubnet',
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=16
                )
            ]
        )

        ipv6Cidr = ec2.CfnVPCCidrBlock(self, "serverVpcIpv6Cidr",
            vpc_id=vpc.vpc_id,
            amazon_provided_ipv6_cidr_block=True
        )

        for idx, subnet in enumerate(typing.cast(typing.List[ec2.Subnet], vpc.public_subnets)):
            subnet.add_route("serverSubnetIpv6Route",
                router_id=vpc.internet_gateway_id,
                router_type=ec2.RouterType.GATEWAY,
                destination_ipv6_cidr_block='::/0'
            )

            cfnSubnet = typing.cast(typing.Optional[ec2.CfnSubnet], subnet.node.default_child)
            cfnSubnet.ipv6_cidr_block = Fn.select(
                idx,
                Fn.cidr(
                    Fn.select(0, vpc.vpc_ipv6_cidr_blocks),
                    256,
                    '64'
                ))
            cfnSubnet.add_depends_on(ipv6Cidr)

        return vpc

    def createSecurityGroup(self):
        # L2 SecurityGroup construct does not support ipv6 well :(
        securityGroup = ec2.CfnSecurityGroup(self, 'serverVpcSecurityGroup',
            vpc_id=self.vpc.vpc_id,
            group_description='Server Vpc Security Group',
            security_group_ingress=[
                ec2.CfnSecurityGroup.IngressProperty(
                    ip_protocol='tcp',
                    from_port=22,
                    to_port=22,
                    cidr_ip=f'{self.ip}/32',
                    description='Allow specific host for ssh'
                ),
                ec2.CfnSecurityGroup.IngressProperty(
                    ip_protocol='tcp',
                    from_port=8333,
                    to_port=8333,
                    cidr_ip='0.0.0.0/0',
                    description='Allow bitcoind'
                ),
                ec2.CfnSecurityGroup.IngressProperty(
                    ip_protocol='tcp',
                    from_port=8333,
                    to_port=8333,
                    cidr_ipv6='::/0',
                    description='Allow bitcoind'
                ),
                ec2.CfnSecurityGroup.IngressProperty(
                    ip_protocol='tcp',
                    from_port=9735,
                    to_port=9735,
                    cidr_ip='0.0.0.0/0',
                    description='Allow lnd'
                ),
                ec2.CfnSecurityGroup.IngressProperty(
                    ip_protocol='tcp',
                    from_port=9735,
                    to_port=9735,
                    cidr_ipv6='::/0',
                    description='Allow lnd'
                ),
                ec2.CfnSecurityGroup.IngressProperty(
                    ip_protocol='tcp',
                    from_port=9911,
                    to_port=9911,
                    cidr_ip='0.0.0.0/0',
                    description='Allow lnd'
                ),
                ec2.CfnSecurityGroup.IngressProperty(
                    ip_protocol='tcp',
                    from_port=9911,
                    to_port=9911,
                    cidr_ipv6='::/0',
                    description='Allow lnd'
                ),
            ],
            security_group_egress=[
                ec2.CfnSecurityGroup.EgressProperty(
                    ip_protocol='-1',
                    from_port=-1,
                    to_port=-1,
                    cidr_ip='0.0.0.0/0',
                    description='Allow all outbound'
                ),
                ec2.CfnSecurityGroup.EgressProperty(
                    ip_protocol='-1',
                    from_port=-1,
                    to_port=-1,
                    cidr_ipv6='::/0',
                    description='Allow all outbound'
                ),
            ]
        )
        securityGroup.apply_removal_policy(RemovalPolicy.RETAIN)

        return securityGroup

    def createServer(self):
        volume = ec2.Volume(self, 'serverVolume2a',
            removal_policy=RemovalPolicy.RETAIN,
            volume_type=ec2.EbsDeviceVolumeType.GP3,
            availability_zone='us-west-2a',
            snapshot_id='snap-0ca71aed81fe73771',
            size=Size.gibibytes(16),
        )
        instance = ec2.Instance(self, 'serverVpcInstance',
            instance_type=ec2.InstanceType('t3a.small'),
            vpc=self.vpc,
            machine_image=ec2.MachineImage.generic_linux({
                'us-west-2': 'ami-03d5c68bab01f3496'
            }),
            role=self.serverRole,
            availability_zone='us-west-2a',
            key_name='tipbotkey', # must be created in advance
        )
        instance.apply_removal_policy(RemovalPolicy.RETAIN)

        instance.node.default_child.volumes = [
            ec2.CfnInstance.VolumeProperty(
                device='/dev/sda2',
                volume_id=volume.volume_id,
            )
        ]

        ec2.CfnEIPAssociation(self, 'serverVpcEIPAssociation',
            eip=ec2.CfnEIP(self, 'serverVpcEIP',
                domain='vpc',
                instance_id=instance.instance_id,
            ).ref,
            instance_id=instance.instance_id
        )

        cfnInstance = typing.cast(typing.Optional[ec2.CfnInstance], instance.node.default_child)
        cfnInstance.ipv6_addresses = [
            ec2.CfnInstance.InstanceIpv6AddressProperty(ipv6_address='2600:1f14:0741:4a00:fedc:ba98:7654:3210')
        ]
        # Need to attach this manually since we have a CfnSecurityGroup, not a SecurityGroup
        cfnInstance.security_group_ids = [
            Fn.get_att(self.securityGroup.logical_id, 'GroupId').to_string()
        ]

    def getIp(self):
        ip1 = requests.get('https://checkip.amazonaws.com').text.strip()
        ip2 = requests.get('https://api.ipify.org').text.strip()

        if not ip1 == ip2:
            raise Exception

        return ip1

    def createLambda(self, functionName, handlerName):
        return lambda_.Function(self, functionName,
            code=self.lambdaCode,
            runtime=lambda_.Runtime.PYTHON_3_8,
            handler=handlerName,
            role=self.lambdaRole,
            layers=[self.lambdaLayer],
            timeout=Duration.seconds(10)
        )

    def createWithdrawWorkflow(self):
        payInvoiceFailed = tasks.LambdaInvoke(self, 'payInvoiceFailed',
            lambda_function=self.createLambda('payInvoiceFailedLambda', 'payInvoiceFailed.payInvoiceFailed'),
            timeout=Duration.seconds(300)
        ).next(sfn.Fail(self, 'tipErrorState'))

        payInvoiceSucceeded = tasks.LambdaInvoke(self, 'payInvoiceSucceeded',
            lambda_function=self.createLambda('payInvoiceSucceededLambda', 'payInvoiceSucceeded.payInvoiceSucceeded'),
            timeout=Duration.seconds(300)
        ).next(sfn.Succeed(self, 'tipSuccessState'))

        self.payInvoice = tasks.StepFunctionsInvokeActivity(self, 'payInvoice',
            activity=sfn.Activity(self, 'payInvoiceActivity'),
            heartbeat=Duration.seconds(86400),
            timeout=Duration.seconds(86400),
        )
        self.payInvoice.add_retry(
            backoff_rate=2,
            errors=['States.Timeout'],
            interval=Duration.seconds(600),
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
            timeout=Duration.seconds(300)
        ).next(sfn.Succeed(self, 'withdrawSuccessState'))

        self.getTipperInvoice = tasks.StepFunctionsInvokeActivity(self, 'getTipperInvoice',
            activity=sfn.Activity(self, 'getTipperInvoiceActivity'),
            heartbeat=Duration.seconds(60),
            timeout=Duration.seconds(86400),
        )
        self.getTipperInvoice.add_retry(
            backoff_rate=1.5,
            errors=['States.Timeout'],
            interval=Duration.seconds(60),
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
                                'cloudwatch:PutMetricData',
                            ],
                            resources=[
                                '*'
                            ]
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
