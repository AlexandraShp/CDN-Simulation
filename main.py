
import simpy

def handle_request(env, server, request_id):
    arrival_time = env.now

    with server.request() as req:
        yield req

        waiting_time = env.now - arrival_time

        # Processing time: 0.05 seconds
        yield env.timeout(0.05)

        response_time = env.now - arrival_time

        print(
            f"Request {request_id}: "
            f"Wait = {waiting_time:.3f}s, "
            f"Response = {response_time:.3f}s"
        )

def generate_requests(env, server):
    for i in range(5):
        env.process(handle_request(env, server, i))
        yield env.timeout(0.02)

env = simpy.Environment()

server = simpy.Resource(env, capacity=1)

env.process(generate_requests(env, server))
env.run()
