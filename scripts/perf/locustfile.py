from locust import HttpUser, between, task


class FBAUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def get_experiments(self):
        self.client.get("/api/v1/experiments")

    @task(2)
    def get_health(self):
        self.client.get("/health")
