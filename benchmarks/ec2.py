from subprocess import check_output, CalledProcessError


def ec2_instance_metadata(arg) -> str | None:
    try:
        return check_output(['curl', '-s', f'http://169.254.169.254/latest/meta-data/{arg}']).decode()
    except CalledProcessError:
        return None


def ec2_instance_id() -> str | None:
    return ec2_instance_metadata('instance-id')


def ec2_instance_type() -> str | None:
    return ec2_instance_metadata('instance-type')
