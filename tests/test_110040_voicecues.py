"""1.10040: what Celestia says on her own, from the journal.

Voice-pack reminders: the phrase to say to a VoiceAttack voice pack at the
moment the journal shows - "Deploy the SRV" after you land, "Dismiss the
ship" once the Rhino is out, "Recall the ship" when every rig is up, and so
on - and dropped when the journal shows it done in the next few seconds.
None more than once in ten minutes.

With Chatty: reactions to what the journal and Status.json show, and a lore
aside now and then when nothing is going on, never in danger.

    python3.12 tests/test_110040_voicecues.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import voice as VO       # noqa: E402
import voicecues as VC   # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


def run(cues, until, step=1.0, start=0.0, **kw):
    """Every line due between start and until, a second at a time."""
    out, t = [], start
    while t <= until:
        line = cues.due(t, **kw)
        if line:
            out.append((round(t), line))
            cues.spoke(t)
        t += step
    return out


T = 1000.0
print("== the lines are hers ==")
check("every cue names a line Celestia has",
      set(VC.HINT_GRACE_S) == set(VO.HINT_IDS) and set(VC.REACTIONS.values()) <= set(VO.REACTION_IDS)
      and set(VO.REACTION_IDS) <= set(VC.REACTIONS.values()) | set(VC.FLAG_REACTIONS.values())
      | {"react_mining_body", "react_big_sale", "react_hold_full"},
      (set(VC.HINT_GRACE_S) ^ set(VO.HINT_IDS)))

print("== Deploy the SRV: after landing, unless you already did ==")
c = VC.Cues()
c.see({"event": "Touchdown", "PlayerControlled": True}, T)
said = run(c, T + 60, start=T)
check("said once its few seconds are up", said == [(T + VC.HINT_GRACE_S["hint_deploy_srv"], "hint_deploy_srv")], said)
c = VC.Cues()
c.see({"event": "Touchdown", "PlayerControlled": True}, T)
c.see({"event": "LaunchSRV", "SRVType": "mev_rhino", "PlayerControlled": True}, T + 8)
said = [x for x in run(c, T + 60, start=T) if x[1] == "hint_deploy_srv"]
check("not said when the Rhino went out first", not said, said)
c = VC.Cues()
c.see({"event": "Touchdown", "PlayerControlled": False}, T)
check("not for the ship coming back on its own", not [x for x in run(c, T + 60, start=T)
                                                      if x[1] == "hint_deploy_srv"])

print("== Dismiss the ship: Rhino out, ship still sat there ==")
c = VC.Cues()
c.see({"event": "Touchdown", "PlayerControlled": True}, T)
c.see({"event": "LaunchSRV", "PlayerControlled": True}, T + 5)
said = [x for x in run(c, T + 120, start=T) if x[1].startswith("hint_")]
check("said after its grace", said == [(T + 5 + VC.HINT_GRACE_S["hint_dismiss_ship"], "hint_dismiss_ship")], said)
c = VC.Cues()
c.see({"event": "Touchdown", "PlayerControlled": True}, T)
c.see({"event": "LaunchSRV", "PlayerControlled": True}, T + 5)
c.see({"event": "Liftoff", "PlayerControlled": False}, T + 20)
check("not when the ship was sent away", not [x for x in run(c, T + 120, start=T) if x[1].startswith("hint_")])
c = VC.Cues()
c.see({"event": "LaunchSRV", "PlayerControlled": False}, T)
check("not for a crewmate's SRV", not run(c, T + 120, start=T))

print("== Recall the ship: every rig up, ship away ==")
c = VC.Cues()
c.see({"event": "Touchdown", "PlayerControlled": True}, T)
c.see({"event": "LaunchSRV", "PlayerControlled": True}, T + 5)
c.see({"event": "Liftoff", "PlayerControlled": False}, T + 10)
c.app("rigs_all_up", T + 500)
said = [x for x in run(c, T + 600, start=T + 400) if x[1].startswith("hint_")]
check("said after its grace", said == [(T + 500 + VC.HINT_GRACE_S["hint_recall_ship"], "hint_recall_ship")], said)
c.app("rigs_all_up", T + 700)
c.see({"event": "Touchdown", "PlayerControlled": False}, T + 710)
check("not when the ship is already coming", not [x for x in run(c, T + 800, start=T + 700)
                                                  if x[1] == "hint_recall_ship"])

print("== Transfer cargo and Board the ship: by the ship ==")
c = VC.Cues()
c.see({"event": "Touchdown", "PlayerControlled": True}, T)
c.see({"event": "LaunchSRV", "PlayerControlled": True}, T + 2)
c.see({"event": "Cargo", "Vessel": "SRV", "Count": 72}, T + 300)
c.status(VC.FLAG_IN_SRV | VC.FLAG_NEAR_SHIP, T + 310)
said = [x for x in run(c, T + 400, start=T + 300) if x[1].startswith("hint_")]
check("a full hold by the ship: Transfer cargo",
      (T + 310 + VC.HINT_GRACE_S["hint_transfer_cargo"], "hint_transfer_cargo") in said, said)
c = VC.Cues()
c.see({"event": "LaunchSRV", "PlayerControlled": True}, T)
c.see({"event": "Cargo", "Vessel": "SRV", "Count": 72}, T + 10)
c.status(VC.FLAG_IN_SRV | VC.FLAG_NEAR_SHIP, T + 20)
c.see({"event": "CargoTransfer", "Transfers": [{"Type": "gold", "Count": 72, "Direction": "toship"}]}, T + 25)
check("not when the cargo has gone across", not [x for x in run(c, T + 100, start=T)
                                                 if x[1] == "hint_transfer_cargo"])
c = VC.Cues()
c.see({"event": "Touchdown", "PlayerControlled": True}, T)
c.see({"event": "LaunchSRV", "PlayerControlled": True}, T + 2)
c.see({"event": "Cargo", "Vessel": "SRV", "Count": 0}, T + 3)
c.app("rigs_all_up", T + 200)
c.status(VC.FLAG_IN_SRV | VC.FLAG_NEAR_SHIP, T + 220)
said = [x for x in run(c, T + 300, start=T + 200) if x[1] == "hint_board_ship"]
check("rigs up, hold empty, by the ship: Board the ship",
      said == [(T + 220 + VC.HINT_GRACE_S["hint_board_ship"], "hint_board_ship")], said)

print("== Apply handbrake: on a pin with it off ==")
c = VC.Cues()
c.see({"event": "LaunchSRV", "PlayerControlled": True}, T)
c.status(VC.FLAG_IN_SRV, T + 1)
c.app("pin_reached", T + 50)
said = [x for x in run(c, T + 70, start=T + 50) if x[1] == "hint_handbrake"]
check("said when it stays off", said == [(T + 50 + VC.HINT_GRACE_S["hint_handbrake"], "hint_handbrake")], said)
c.app("pin_reached", T + 900)
c.status(VC.FLAG_IN_SRV | VC.FLAG_HANDBRAKE, T + 902)
check("not when it goes on", not [x for x in run(c, T + 960, start=T + 900) if x[1] == "hint_handbrake"])

print("== no nagging ==")
c = VC.Cues()
c.see({"event": "Touchdown", "PlayerControlled": True}, T)
first = run(c, T + 60, start=T)
c.see({"event": "Touchdown", "PlayerControlled": True}, T + 100)
again = run(c, T + 200, start=T + 61)
check("the same reminder not again inside ten minutes", first and not again, (first, again))
c = VC.Cues()
c.see({"event": "Touchdown", "PlayerControlled": True}, T)
check("reminders off: nothing", not run(c, T + 60, start=T, hints=False))

print("== Chatty: reactions ==")
c = VC.Cues()
c.see({"event": "LaunchSRV", "PlayerControlled": True}, T)
check("not without Chatty", not [x for x in run(c, T + 10, start=T) if x[1].startswith("react_")])
c = VC.Cues()
c.see({"event": "LaunchSRV", "PlayerControlled": True}, T)
said = run(c, T + 10, start=T, chatty=True)
check("with Chatty, the Rhino going out", said and said[0][1] == "react_launch_srv", said)
c = VC.Cues()
c.see({"event": "MarketSell", "Type": "gold", "Count": 700, "TotalSale": 80000000}, T)
c.see({"event": "MarketSell", "Type": "gold", "Count": 1, "TotalSale": 9000}, T + 200)
said = [x[1] for x in run(c, T + 400, start=T, chatty=True) if x[1].startswith("react_")]
check("a big sale, not a small one", said == ["react_big_sale"], said)
c = VC.Cues()
c.see({"event": "FSSBodySignals", "Signals": [{"Type": "$PlanetaryMiningLocation_Name;", "Count": 3}]}, T)
c.see({"event": "SAASignalsFound", "Signals": [{"Type": "$SAA_SignalType_Geological;", "Count": 2}]}, T + 200)
said = [x[1] for x in run(c, T + 400, start=T, chatty=True) if x[1].startswith("react_")]
check("mining locations found, not other signals", said == ["react_mining_body"], said)
c = VC.Cues()
c.status(VC.FLAG_OVERHEAT, T)
c.status(VC.FLAG_OVERHEAT, T + 1)
c.status(0, T + 2)
c.status(VC.FLAG_OVERHEAT, T + 20)
said = [x[1] for x in run(c, T + 60, start=T, chatty=True)]
check("over heating, said as it starts, not every second, not again at once", said == ["react_overheat"], said)
c = VC.Cues()
for i in range(5):
    c.see({"event": "FSDJump"}, T + i * 5)
said = run(c, T + 60, start=T, chatty=True)
check("a burst of jumps is one reaction", len(said) == 1, said)

print("== Chatty: lore asides ==")
c = VC.Cues()
said = run(c, T + 3600, start=T, chatty=True)
lore = [x for x in said if x[1].startswith("lore_")]
check("now and then when nothing is going on", 3 <= len(lore) <= 3600 // VC.LORE_EVERY_S + 1, lore)
check("never two the same in a row", all(a[1] != b[1] for a, b in zip(lore, lore[1:])))
check("never sooner than they should be", all(b[0] - a[0] >= VC.LORE_EVERY_S for a, b in zip(lore, lore[1:])))
c = VC.Cues()
c.status(VC.FLAG_IN_DANGER, T)
check("never in danger", not [x for x in run(c, T + 3600, start=T, chatty=True) if x[1].startswith("lore_")])
c = VC.Cues()
check("never while busy", not run(c, T + 3600, start=T, chatty=True, busy=True))
check("not without Chatty", not run(VC.Cues(), T + 3600, start=T))

print("== a quiet gap between her own lines ==")
c = VC.Cues()
c.see({"event": "LaunchSRV", "PlayerControlled": True}, T)
c.see({"event": "Touchdown", "PlayerControlled": True}, T)
said = run(c, T + 120, start=T, chatty=True)
check("never two of her own lines closer than the gap",
      all(b[0] - a[0] >= VC.OWN_GAP_S for a, b in zip(said, said[1:])), said)

print("== only what happens now, not what the journal is read back from ==")
import calendar, json, tempfile, time  # noqa: E402,E401
NOW = 1793860000.0


def stamp(when):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(when))


check("an event the game has just written is fresh",
      VC.fresh({"event": "Touchdown", "timestamp": stamp(NOW - 5)}, NOW))
check("one read back from an hour ago is not", not VC.fresh({"event": "Touchdown", "timestamp": stamp(NOW - 3600)}, NOW))
check("nor one with no time, or a time that is not one",
      not VC.fresh({"event": "Touchdown"}, NOW) and not VC.fresh({"event": "Touchdown", "timestamp": "soon"}, NOW))

print("== the reminders switch: on by itself when a voice pack is there ==")
check("left alone, it follows what was found", VC.hints_wanted(None, True) is True and VC.hints_wanted(None, False) is False)
check("once set, it is what was set", VC.hints_wanted(False, True) is False and VC.hints_wanted(True, False) is True)
check("saving Settings with the switch as it was shown keeps it following",
      VC.kept_auto(None, True, True) is None and VC.kept_auto(None, False, False) is None)
check("changing it makes it the commander's own", VC.kept_auto(None, False, True) is False
      and VC.kept_auto(None, True, False) is True and VC.kept_auto(True, True, True) is True)

import voiceattack as VA  # noqa: E402
env = {"ProgramFiles": r"C:\Program Files", "ProgramFiles(x86)": r"C:\Program Files (x86)"}
vdf = '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"C:\\\\Program Files (x86)\\\\Steam"\n\t}\n' \
      '\t"1"\n\t{\n\t\t"path"\t\t"E:\\\\SteamLibrary"\n\t}\n}\n'
check("Steam's library list read for every library", VA.steam_libraries(vdf) == [r"C:\Program Files (x86)\Steam",
                                                                               r"E:\SteamLibrary"],
      VA.steam_libraries(vdf))
places = VA.sounds_folders(env, VA.steam_libraries(vdf))
check("VoiceAttack's Sounds folder looked for where VoiceAttack and Steam install it",
      r"C:\Program Files (x86)\VoiceAttack\Sounds" in places
      and r"E:\SteamLibrary\steamapps\common\VoiceAttack\Sounds" in places
      and r"C:\Program Files\VoiceAttack 2\Sounds" in places, places)
check("no pack is named in looking for one",
      not any(word in open(VA.__file__, encoding="utf-8").read().lower() for word in ("hcs", "hcspack")))
SOUNDS = tempfile.mkdtemp(prefix="edsmt-sounds-")
open(os.path.join(SOUNDS, "empty.txt"), "w").close()
check("a Sounds folder with only VoiceAttack's own file in it: no pack", not VA.has_sound_packs([SOUNDS]))
os.makedirs(os.path.join(SOUNDS, "Some Voice"))
check("a folder in it is a pack, as VoiceAttack's own guide has them",
      VA.has_sound_packs([os.path.join(SOUNDS, "missing"), SOUNDS]))
check("no folder at all: no pack, and nothing raised", not VA.has_sound_packs(["/nowhere/at/all"]))

print("== the journal reader hands them over ==")
import journal as JN  # noqa: E402
GAME = tempfile.mkdtemp(prefix="edsmt-cues-")
lines = [{"timestamp": stamp(NOW), "event": "Fileheader", "part": 1, "gameversion": "4.4.1.0"},
         {"timestamp": stamp(NOW), "event": "Touchdown", "PlayerControlled": True, "Body": "Ega 1"},
         {"timestamp": stamp(NOW), "event": "LaunchSRV", "SRVType": "mev_rhino", "PlayerControlled": True},
         {"timestamp": stamp(NOW), "event": "Cargo", "Vessel": "SRV", "Count": 72},
         {"timestamp": stamp(NOW), "event": "Music", "MusicTrack": "Exploration"}]
with open(os.path.join(GAME, "Journal.2026-11-05T070000.01.log"), "w", encoding="utf-8") as handle:
    handle.write("\n".join(json.dumps(e) for e in lines) + "\n")
with open(os.path.join(GAME, "Status.json"), "w", encoding="utf-8") as handle:
    json.dump({"timestamp": stamp(NOW), "event": "Status", "Flags": VC.FLAG_IN_SRV | VC.FLAG_NEAR_SHIP,
               "Flags2": 0}, handle)
reader = JN.JournalWatcher(GAME)
reader.poll()
taken = reader.take_voice_events()
check("the events her cues read, in order, nothing else",
      [e["event"] for e in taken] == ["Touchdown", "LaunchSRV", "Cargo"], [e.get("event") for e in taken])
check("and taking them empties the list", reader.take_voice_events() == [])
check("Status.json's flags kept for her", reader.flags == VC.FLAG_IN_SRV | VC.FLAG_NEAR_SHIP, reader.flags)
check("her events are never skipped unread", not any(JN.skipped(n) for n in VC.EVENTS))

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
