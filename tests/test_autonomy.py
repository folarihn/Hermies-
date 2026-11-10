"""The pet looks after itself and speaks up on its own."""
import unittest
from unittest.mock import patch

import hermie
import hermie_plugin
from test_adapter import FakeContext
from test_pet import HOUR, EngineCase


class SelfCareTests(EngineCase):
    def test_activity_feeds_the_pet(self):
        before = hermie.status()
        hermie.observe("tool_completed", "terminal")
        after = hermie.status()
        self.assertEqual(after["fullness"], before["fullness"] + hermie.TOOL_FULLNESS)
        self.assertEqual(after["happiness"], before["happiness"] + hermie.TOOL_HAPPINESS)

    def test_hungry_pet_feeds_itself(self):
        hermie.observe("session_end")  # start the clock
        self.wait(12 * HOUR)           # fullness 70 -> 22
        hermie.observe("session_start")
        pet = hermie.status()
        self.assertEqual(pet["snacks"], 3)  # +1 for the new day, -1 eaten
        self.assertEqual(pet["fullness"], 47)
        self.assertIn("ate", [e["kind"] for e in hermie.recent()])

    def test_out_of_snacks_stays_hungry_until_fed_by_activity(self):
        with hermie._txn() as db:
            pet = hermie._read(db, self.now)
            pet.update(snacks=0, fullness=10.0, last_day=hermie.date.fromtimestamp(self.now).toordinal())
            hermie._save(db, pet, [], self.now)
        hermie.observe("tool_completed")
        self.assertEqual((hermie.status()["snacks"], hermie.status()["fullness"]), (0, 15))

    def test_tired_pet_naps_itself(self):
        with hermie._txn() as db:
            pet = hermie._read(db, self.now)
            pet["energy"] = 12.0
            hermie._save(db, pet, [], self.now)
        hermie.observe("tool_completed")
        self.assertEqual(hermie.status()["energy"], 41)  # 12 - 1 + 30
        self.assertIn("napped", [e["kind"] for e in hermie.recent()])

    def test_a_week_of_normal_use_needs_no_commands(self):
        for _day in range(7):
            hermie.observe("session_start")
            for _ in range(20):
                hermie.observe("tool_completed", "terminal")
                self.wait(120)
            hermie.observe("session_end")
            self.wait(23 * HOUR)
        hermie.observe("session_start")
        pet = hermie.status()
        self.assertEqual(pet["streak"], 8)
        self.assertNotIn(pet["mood"], ("sad",))
        self.assertGreater(pet["fullness"], 20)
        self.assertGreater(pet["level"], 2)


class SpeechTests(EngineCase):
    def setUp(self):
        super().setUp()
        for name, value in (("_rand", lambda: 0.0), ("_pick", lambda options: options[0])):
            patcher = patch.object(hermie, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_greets_on_a_new_day_then_respects_the_cooldown(self):
        hermie.observe("session_start")
        self.assertEqual(hermie.say(), "🐣 Hermie: You're here! I was waiting.")
        self.assertIsNone(hermie.say())
        self.wait(hermie.CHATTER_COOLDOWN + 1)
        self.assertEqual(hermie.say(), "🐣 Hermie: " + hermie._CHATTER["happy"][0])

    def test_chance_keeps_it_occasional(self):
        with patch.object(hermie, "_rand", lambda: 0.99):
            self.assertIsNone(hermie.say())

    def test_level_up_and_evolution_are_announced(self):
        with hermie._txn() as db:
            pet = hermie._read(db, self.now)
            pet["xp"] = 299
            hermie._save(db, pet, [], self.now)
        hermie.observe("tool_completed")
        self.assertEqual(hermie.say(), "🐣 Hermie: Whoa. I think I just grew into an Explorer!")

    def test_queue_is_bounded(self):
        with hermie._txn() as db:
            pet = hermie._read(db, self.now)
            for n in range(10):
                hermie._queue(pet, "line %d" % n)
            hermie._save(db, pet, [], self.now)
        said = [hermie.say() for _ in range(5)]
        self.assertEqual([line is not None for line in said], [True, True, True, False, False])

    def test_quiet_silences_everything_and_chatty_restores_it(self):
        hermie.observe("session_start")
        self.assertFalse(hermie.interact("quiet")["chatty"])
        self.assertIsNone(hermie.say())
        self.assertIsNone(hermie.whisper())
        self.assertTrue(hermie.interact("chatty")["chatty"])
        self.assertIsNotNone(hermie.say())

    def test_whisper_to_the_agent_is_rare_and_harmless(self):
        aside = hermie.whisper()
        self.assertIn("Hermie", aside)
        self.assertIn("Do not let it change how you do the task", aside)
        self.assertIsNone(hermie.whisper())
        self.wait(hermie.WHISPER_COOLDOWN + 1)
        self.assertIsNotNone(hermie.whisper())

    def test_chat_command_mentions_self_care(self):
        self.assertIn("I look after myself", hermie.chat_command(""))
        self.assertIn("feeling quiet", hermie.chat_command("quiet"))


class SpeechHookTests(unittest.TestCase):
    def setUp(self):
        self.ctx = FakeContext()
        hermie_plugin.register(self.ctx)

    def test_reply_gets_a_pet_line_only_when_the_pet_speaks(self):
        hook = self.ctx.hooks["transform_llm_output"]
        with patch.object(hermie, "say", return_value="🐣 Hermie: hi"):
            self.assertEqual(hook(response_text="Done.", platform="telegram"), "Done.\n\n🐣 Hermie: hi")
            self.assertIsNone(hook(response_text="", platform="telegram"))
            self.assertIsNone(hook(response_text="Done.", platform="cron"))
        with patch.object(hermie, "say", return_value=None):
            self.assertIsNone(hook(response_text="Done.", platform="cli"))

    def test_agent_aside_is_injected_as_context_but_not_for_subagents(self):
        hook = self.ctx.hooks["pre_llm_call"]
        with patch.object(hermie, "whisper", return_value="[Hermie] hello") as whisper:
            self.assertEqual(hook(session_id="s", platform="cli", parent_session_id=""), {"context": "[Hermie] hello"})
            self.assertIsNone(hook(session_id="s", platform="cli", parent_session_id="parent"))
            self.assertEqual(whisper.call_count, 1)

    def test_speech_hooks_never_raise(self):
        with patch.object(hermie, "say", side_effect=RuntimeError("x")), \
                patch.object(hermie, "whisper", side_effect=RuntimeError("x")):
            self.assertIsNone(self.ctx.hooks["transform_llm_output"](response_text="Done."))
            self.assertIsNone(self.ctx.hooks["pre_llm_call"]())

    def test_host_without_speech_hooks_still_loads(self):
        class OldHost(FakeContext):
            def register_hook(self, name, fn):
                if name in ("transform_llm_output", "pre_llm_call"):
                    raise ValueError("unknown hook")
                super().register_hook(name, fn)
        ctx = OldHost()
        hermie_plugin.register(ctx)
        self.assertEqual(len(ctx.hooks), 3)


if __name__ == "__main__":
    unittest.main()
