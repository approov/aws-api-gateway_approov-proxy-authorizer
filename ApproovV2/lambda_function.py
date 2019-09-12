import re
import time
import json
import datetime
import base64
import jwt

# Set the token secret from the admin portal as a constant
# Secret is a base64 encoded string.
SECRET = "secret"

def lambda_handler(event, context):
    # assume token is valid until exception.
    TokenValid = True
    # Authorization token is passed in via a custom http header
    # The header is configurable in the API Gateway admin interface
    token = event['authorizationToken']
    # Use the entire token as the Principal ID
    principalId = event['authorizationToken']
    # setup return policy settings
    tmp = event['methodArn'].split(':')
    apiGatewayArnTmp = tmp[5].split('/')
    awsAccountId = tmp[4]
    policy = AuthPolicy(principalId, awsAccountId)
    policy.restApiId = apiGatewayArnTmp[0]
    policy.region = tmp[3]
    policy.stage = apiGatewayArnTmp[1]

    # Decode the token using the per-customer secret downloaded from the
    # Approov admin portal
    try:
        tokenContents = jwt.decode(token, SECRET, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        # Signature has expired, token is bad
        TokenValid = False
    except:
        # Token could not be decoded, token is bad, or signature expired.
        TokenValid = False
        
    if (TokenValid):
       # Retrieve the time from the token
       if 'exp' in tokenContents:
          expiration = (tokenContents['exp'])
          # Convert to the appropriate format for the condition in the policy
          expirationTime = datetime.datetime.utcfromtimestamp(expiration).strftime('%Y-%m-%dT%H:%M:%SZ')
       else:
          TokenValid = False

    if (TokenValid):
      # Token and cliams are good, setup the access conditions.
      conditions = {
         "DateLessThanEquals": {
            "aws:CurrentTime": expirationTime
         }
      }
      # Allow all methods, restricted to those which match condition
      policy.allowMethodWithConditions(HttpVerb.ALL, '*', conditions)
    else:
      # if token invalid, deny access when token presented.
      # Deny all methods, restricted to those which match condition
      policy.denyMethod(HttpVerb.ALL, '*')

    '''finally, build the policy and exit the function using return'''
    return policy.build()


class HttpVerb:
    GET     = 'GET'
    POST    = 'POST'
    PUT     = 'PUT'
    PATCH   = 'PATCH'
    HEAD    = 'HEAD'
    DELETE  = 'DELETE'
    OPTIONS = 'OPTIONS'
    ALL     = '*'


class AuthPolicy(object):
    awsAccountId = ''
    '''The AWS account id the policy will be generated for. This is used to create the method ARNs.'''
    principalId = ''
    '''The principal used for the policy, this should be a unique identifier for the end user.'''
    version = '2012-10-17'
    '''The policy version used for the evaluation. This should always be '2012-10-17' '''
    pathRegex = '^[/.a-zA-Z0-9-\*]+$'
    '''The regular expression used to validate resource paths for the policy'''

    '''these are the internal lists of allowed and denied methods. These are lists
    of objects and each object has 2 properties: A resource ARN and a nullable
    conditions statement.
    the build method processes these lists and generates the approriate
    statements for the final policy'''
    allowMethods = []
    denyMethods = []

    restApiId = '*'
    '''The API Gateway API id. By default this is set to '*' '''
    region = '*'
    '''The region where the API is deployed. By default this is set to '*' '''
    stage = '*'
    '''The name of the stage used in the policy. By default this is set to '*' '''

    def __init__(self, principal, awsAccountId):
        self.awsAccountId = awsAccountId
        self.principalId = principal
        self.allowMethods = []
        self.denyMethods = []

    def _addMethod(self, effect, verb, resource, conditions):
        '''Adds a method to the internal lists of allowed or denied methods. Each object in
        the internal list contains a resource ARN and a condition statement. The condition
        statement can be null.'''
        if verb != '*' and not hasattr(HttpVerb, verb):
            raise NameError('Invalid HTTP verb ' + verb + '. Allowed verbs in HttpVerb class')
        resourcePattern = re.compile(self.pathRegex)
        if not resourcePattern.match(resource):
            raise NameError('Invalid resource path: ' + resource + '. Path should match ' + self.pathRegex)

        if resource[:1] == '/':
            resource = resource[1:]

        resourceArn = (
            'arn:aws:execute-api:' +
            self.region + ':' +
            self.awsAccountId + ':' +
            self.restApiId + '/' +
            self.stage + '/' +
            verb + '/' +
            resource)

        if effect.lower() == 'allow':
            self.allowMethods.append({
                'resourceArn' : resourceArn,
                'conditions' : conditions
            })
        elif effect.lower() == 'deny':
            self.denyMethods.append({
                'resourceArn' : resourceArn,
                'conditions' : conditions
            })

    def _getEmptyStatement(self, effect):
        '''Returns an empty statement object prepopulated with the correct action and the
        desired effect.'''
        statement = {
            'Action': 'execute-api:Invoke',
            'Effect': effect[:1].upper() + effect[1:].lower(),
            'Resource': []
        }

        return statement

    def _getStatementForEffect(self, effect, methods):
        '''This function loops over an array of objects containing a resourceArn and
        conditions statement and generates the array of statements for the policy.'''
        statements = []

        if len(methods) > 0:
            statement = self._getEmptyStatement(effect)

            for curMethod in methods:
                if curMethod['conditions'] is None or len(curMethod['conditions']) == 0:
                    statement['Resource'].append(curMethod['resourceArn'])
                else:
                    conditionalStatement = self._getEmptyStatement(effect)
                    conditionalStatement['Resource'].append(curMethod['resourceArn'])
                    conditionalStatement['Condition'] = curMethod['conditions']
                    statements.append(conditionalStatement)

            if statement['Resource']:
                statements.append(statement)

        return statements

    def allowAllMethods(self):
        '''Adds a '*' allow to the policy to authorize access to all methods of an API'''
        self._addMethod('Allow', HttpVerb.ALL, '*', [])

    def denyAllMethods(self):
        '''Adds a '*' allow to the policy to deny access to all methods of an API'''
        self._addMethod('Deny', HttpVerb.ALL, '*', [])

    def allowMethod(self, verb, resource):
        '''Adds an API Gateway method (Http verb + Resource path) to the list of allowed
        methods for the policy'''
        self._addMethod('Allow', verb, resource, [])

    def denyMethod(self, verb, resource):
        '''Adds an API Gateway method (Http verb + Resource path) to the list of denied
        methods for the policy'''
        self._addMethod('Deny', verb, resource, [])

    def allowMethodWithConditions(self, verb, resource, conditions):
        '''Adds an API Gateway method (Http verb + Resource path) to the list of allowed
        methods and includes a condition for the policy statement. More on AWS policy
        conditions here: http://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements.html#Condition'''
        self._addMethod('Allow', verb, resource, conditions)

    def denyMethodWithConditions(self, verb, resource, conditions):
        '''Adds an API Gateway method (Http verb + Resource path) to the list of denied
        methods and includes a condition for the policy statement. More on AWS policy
        conditions here: http://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements.html#Condition'''
        self._addMethod('Deny', verb, resource, conditions)

    def build(self):
        '''Generates the policy document based on the internal lists of allowed and denied
        conditions. This will generate a policy with two main statements for the effect:
        one statement for Allow and one statement for Deny.
        Methods that includes conditions will have their own statement in the policy.'''
        if ((self.allowMethods is None or len(self.allowMethods) == 0) and
            (self.denyMethods is None or len(self.denyMethods) == 0)):
            raise NameError('No statements defined for the policy')

        policy = {
            'principalId' : self.principalId,
            'policyDocument' : {
                'Version' : self.version,
                'Statement' : []
            }
        }

        policy['policyDocument']['Statement'].extend(self._getStatementForEffect('Allow', self.allowMethods))
        policy['policyDocument']['Statement'].extend(self._getStatementForEffect('Deny', self.denyMethods))

        return policy
