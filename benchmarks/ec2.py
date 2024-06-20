from subprocess import check_output, CalledProcessError


def ec2_instance_id() -> str | None:
    try:
        return check_output(['curl', '-s', 'http://169.254.169.254/latest/meta-data/instance-id']).decode()
    except CalledProcessError:
        return None
