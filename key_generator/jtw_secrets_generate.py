import secrets
import os

def generate_jwt_secrets(local_secret_path="local_jwt_secret.txt", deploy_secret_path="deploy_jwt_secret.txt"):
    """
    Generates two JWT secret keys, one for local development and one for deployment.
    Stores them in separate files.

    Args:
        local_secret_path (str): Path to the file for the local secret.
        deploy_secret_path (str): Path to the file for the deploy secret.
    """

    local_secret = secrets.token_hex(32)  # Generates a 32-byte (256-bit) random hex string
    deploy_secret = secrets.token_hex(32)

    try:
        with open(local_secret_path, "w") as f:
            f.write(local_secret)
        print(f"Local JWT secret written to: {local_secret_path}")

        with open(deploy_secret_path, "w") as f:
            f.write(deploy_secret)
        print(f"Deployment JWT secret written to: {deploy_secret_path}")

    except OSError as e:
        print(f"Error writing JWT secrets: {e}")

def get_jwt_secret(is_local=True, local_secret_path="local_jwt_secret.txt", deploy_secret_path="deploy_jwt_secret.txt"):
    """
    Retrieves the appropriate JWT secret key based on the environment.

    Args:
        is_local (bool): True for local environment, False for deployment.
        local_secret_path (str): Path to the local secret file.
        deploy_secret_path (str): Path to the deploy secret file.

    Returns:
        str: The JWT secret key, or None if an error occurs.
    """
    secret_path = local_secret_path if is_local else deploy_secret_path

    try:
        with open(secret_path, "r") as f:
            return f.read().strip()  # Remove any trailing whitespace
    except FileNotFoundError:
        print(f"JWT secret file not found: {secret_path}")
        return None
    except OSError as e:
        print(f"Error reading JWT secret: {e}")
        return None

# Example usage:
generate_jwt_secrets() #create the files if they do not exist.

# Example of retrieving the secret:
local_secret = get_jwt_secret(is_local=True)
deploy_secret = get_jwt_secret(is_local=False)

if local_secret:
    print(f"Local Secret: {local_secret[0:8]}... (first 8 characters)") #print only a small portion.
if deploy_secret:
    print(f"Deploy Secret: {deploy_secret[0:8]}... (first 8 characters)") #print only a small portion.

# Example of usage within a flask app.
# inside of a flask app, the is_local variable could be determined by an environment variable.
# is_local = os.environ.get("FLASK_ENV") == "development"
# secret_key = get_jwt_secret(is_local=is_local)
