import docker


class SandboxRunner:
    def __init__(self, image_name):
        self.client = docker.from_env()
        self.image_name = image_name

    def run_code(self, code):
        container = self.client.containers.run(
            self.image_name,
            f"python -c '{code}'",
            detach=True,
            stderr=True,
            stdout=True
        )

        output = container.logs().decode("utf-8")
        container.remove()

        return output
