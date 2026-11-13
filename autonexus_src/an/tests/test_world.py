import unittest

from autonexus.algorithms import dijkstra, graph
from autonexus.world import World, federated_summary


def run(world, until, limit=4000):
    for _ in range(limit):
        if world.phase == until:
            return True
        world.tick(.1)
    return world.phase == until


def shortage_world():
    world = World()
    for destination in world.dataset["dealerships"]:
        for part in world.dataset["parts"]:
            demand = sum(row["qty"] for row in world.db["ros"]
                         if row["dealer"] == destination and row["part"] == part)
            on_hand = world.db["stock"][destination].get(part, 0)
            required = max(demand, on_hand + 1)
            configured = world.configure(destination, part, required)
            if configured["ok"] and world.start()["ok"]:
                world.reset(destination, part, required)
                return world
    raise AssertionError("The telemetry dataset contains no feasible shortage scenario.")


class WorldTests(unittest.TestCase):
    def test_dataset_options_and_custom_inputs(self):
        world = World()
        state = world.state()
        self.assertEqual(state["destinations"], world.dataset["dealerships"])
        self.assertEqual({part["id"] for part in state["parts"]},
                         set(world.dataset["parts"]))
        self.assertEqual({site["id"] for site in state["sites"]},
                         set(world.dataset["sites"]))
        destination = state["destinations"][0]
        part = state["parts"][0]["id"]
        result = world.configure(destination, part, required_qty=5)
        self.assertTrue(result["ok"])
        self.assertEqual((world.dest, world.part, world.required_qty),
                         (destination, part, 5))
        demand = sum(row["qty"] for row in world.db["ros"]
                     if row["dealer"] == destination and row["part"] == part)
        self.assertTrue(world.configure(destination, part)["ok"])
        self.assertEqual(world.required_qty, demand)

    def test_invalid_inputs_are_rejected(self):
        world = World()
        self.assertFalse(world.configure("unknown", world.part)["ok"])
        self.assertFalse(world.configure(world.dest, "unknown")["ok"])
        self.assertFalse(world.configure(world.dest, world.part, 0)["ok"])
        self.assertFalse(world.configure(world.dest, world.part, source=world.dest)["ok"])

    def test_approval_gate_holds_delivery_and_inventory(self):
        world = shortage_world()
        before = dict(world.state()["stock"])
        self.assertTrue(world.start()["ok"])
        self.assertTrue(run(world, "awaiting_approval"))
        state = world.state()
        self.assertFalse(state["rider"]["visible"])
        self.assertEqual(state["progress"], 0)
        self.assertEqual(state["stock"], before)
        self.assertFalse(world.approve("supplier")["ok"])
        for _ in range(100):
            world.tick(.1)
        self.assertEqual(world.state()["stock"], before)
        self.assertEqual(world.phase, "awaiting_approval")

    def test_reject_means_no_delivery_and_no_stock_change(self):
        world = shortage_world()
        before = dict(world.state()["stock"])
        world.start()
        self.assertTrue(run(world, "awaiting_approval"))
        self.assertTrue(world.reject()["ok"])
        for _ in range(300):
            world.tick(.1)
        state = world.state()
        self.assertEqual(state["phase"], "rejected")
        self.assertEqual(state["stock"], before)
        self.assertFalse(state["rider"]["visible"])

    def test_full_flow_and_data_driven_road_reroute(self):
        world = shortage_world()
        world.start()
        self.assertTrue(run(world, "awaiting_approval"))
        self.assertTrue(world.approve("admin")["ok"])
        self.assertTrue(run(world, "in_transit"))
        for _ in range(5):
            world.tick(.1)
        before = dict(world.state()["stock"])

        reroute_edge = None
        for edge in zip(world.route, world.route[1:]):
            candidate_graph = graph(
                world.blocked + [edge],
                nodes=world.network["nodes"],
                edge_map=world.network["edge_map"],
            )
            if dijkstra(candidate_graph, edge[0], world.dest)["path"]:
                reroute_edge = edge
                break
        self.assertIsNotNone(reroute_edge, "Expected an alternate route in the dataset.")
        old_route = list(world.route)
        self.assertTrue(world.block(reroute_edge)["ok"])
        self.assertNotEqual(world.route, old_route)
        self.assertEqual(world.state()["stock"], before)
        self.assertNotIn(list(reroute_edge), [
            world.route[index:index + 2] for index in range(len(world.route) - 1)
        ])

        self.assertTrue(run(world, "recovered"))
        state = world.state()
        self.assertTrue(state["verified"])
        self.assertTrue(state["audit"]["valid"])
        self.assertGreaterEqual(state["stock"][world.dest], state["need"])
        self.assertTrue(state["transfer"])
        self.assertTrue(state["events"])
        self.assertIn("route_recalculated", [event["kind"] for event in state["events"]])

    def test_no_feasible_source_prevents_start(self):
        world = shortage_world()
        for site in world.db["stock"]:
            if site != world.dest:
                world.db["stock"][site][world.part] = 0
        self.assertFalse(world.start()["ok"])

    def test_reset_preserves_custom_dataset_selection(self):
        world = shortage_world()
        selected = (world.dest, world.part, world.required_qty)
        world.reset()
        self.assertEqual((world.dest, world.part, world.required_qty), selected)

    def test_federated_summary_matches_round_curve(self):
        result = federated_summary()
        self.assertEqual(len(result["fed_f1_curve"]), result["rounds"])
        self.assertTrue(result["clients"])


if __name__ == "__main__":
    unittest.main()
