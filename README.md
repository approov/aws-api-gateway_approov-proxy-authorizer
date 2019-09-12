# Approov Proxy Authorizer for the AWS API Gateway

These Python code examples are for implementing [Approov](https://approov.io/approov-in-detail.html) as a Proxy Authorizer in the AWS API Gateway.

For production usage please use the package that best suites your framework of choice.


## AWS API Gateway Authorizer

The `ApproovV2/lambda_function.py` will implement a proxy authorizer for Approov tokens in an AWS API Gateway.

The Approov authorizer will validate the Approov token for being signed correctly, not being expired, and optionally can
validate if the token binding on it matches the token binding value in the header of the request.

### Response Codes

#### If invalid returns:

* 401 - when the Approov token cannot be decoded.
* 403 - when the Approov token can be decoded but is expired or the token binding doesn't match with the value in the header of the request. Also returns a 403 for when allow policy conditions fail.

#### If valid returns:

* 200 - when the Approov token is valid and policy conditions are met. The body will contain the data for the response to the request.

### Requirements

* Authorizer Runtime: Python 3
* Python dependencies: PyJWT


## Issue Reporting

If you have found a bug please report them [here](https://github.com/approov/aws-api-gateway_approov-proxy-authorizer/issues/new).


## License

This project is licensed under the MIT license. See the [LICENSE](LICENSE) file for more info.
