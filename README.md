
# Lightning Network Reddit Tip Bot

You'll need to create an IAM role ahead of time with full permissions (or add specific permissions as needed) to deploy using the cdk/sam CLI

To manually create a virtualenv on MacOS and Linux:

```
$ python -m venv .env
```

After the init process completes and the virtualenv is created, you can use the following
step to activate your virtualenv on linux, macOS, or windows mingw

```
$ source .env/Scripts/activate
```

If you are a Windows platform, you would activate the virtualenv like this:

```
% .env\Scripts\activate.bat
```

Once the virtualenv is activated, you can install the required dependencies.

```
$ pip install -r requirements.txt
$ pip install wheel
```

At this point you can now synthesize the CloudFormation template for this code.

```
$ cdk synth
```

To add additional dependencies, for example other CDK libraries, just add
them to your `setup.py` file and rerun the `pip install -r requirements.txt`
command.

 To bootstrap in a new region/account

 cdk --profile zzz bootstrap 

 where zzz is a profile specified in ~/.aws/credentials

 To deploy

 cdk --profile zzz deploy CdkStack

To deploy sam stack

./deploy.sh zzz

## Other useful commands

 * `cdk ls`                        list all stacks in the app
 * `cdk synth`                     emits the synthesized CloudFormation template
 * `cdk deploy --profile dev`      deploy this stack to your default AWS account/region
 * `cdk diff --profile dev`        compare deployed stack with current state
 * `cdk docs`                      open CDK documentation
