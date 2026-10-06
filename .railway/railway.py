from railway_sdk import define_railway, preserve, project, service

# A partial: this repository owns one service, so a plan from here leaves the
# rest of the environment alone.
PARTIAL = "nonogram"


@define_railway
def main(_ctx=None):
    nonogram = service(
        "nonogram",
        # Secrets stay dashboard-managed. preserve() marks a variable as
        # existing and not this file's to define; an undeclared one is a
        # variable a plan proposes deleting.
        env={"ORIGIN_SECRET": preserve()},
        build={"builder": "DOCKERFILE"},
        deploy={
            "healthcheckPath": "/health",
            "restartPolicyType": "ON_FAILURE",
            "restartPolicyMaxRetries": 5,
            # Scale to zero when idle. The gateway's pass gate is what wakes
            # this, so an always-on replica would cost money to answer nobody.
            "sleepApplication": True,
        },
    )
    return project("backends", resources=[nonogram])
