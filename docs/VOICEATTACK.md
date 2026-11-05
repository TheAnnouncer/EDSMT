# A VoiceAttack profile for EDSMT

EDSMT can write a profile for VoiceAttack whose spoken commands press the
keys you have bound in EDSMT. This page says what the file is, what
VoiceAttack's own documentation says about the format, and what is not
confirmed.

## Making it and bringing it in

1. EDSMT: **Settings → Keys → VoiceAttack → Make a VoiceAttack profile**.
   It writes `Radio Raxxla EDSMT.vap` into EDSMT's data folder and says
   where that is. It uses the keys as they are on the Keys page at that
   moment, so make it again after changing a key.
2. VoiceAttack: in the profile list pick **Import Profile**, browse to the
   file and press **Open** ([VoiceAttack how-to][howto]). A profile with
   the same name as one you already have is brought in with `-1` on the end
   of its name ([how-to][howto]).

Importing a profile needs the registered version of VoiceAttack ([help][help]).

## The commands

| Say | Presses the key for | As EDSMT ships |
|---|---|---|
| mark signal | Log the signal and set the centre | Alt+1 |
| set border | Survey border here | Alt+2 |
| mark deposit | Mark the deposit | Alt+3 |
| rig one down … rig six down | Rig 1 down … Rig 6 down | Alt+4 … Alt+9 |
| rigs up | Every rig up | AltGr+0 (Ctrl+Alt+0) |
| update deposit | Update the deposit I am on | AltGr+3 (Ctrl+Alt+3) |
| next waypoint | Survey waypoint: next | not set |
| overlay | Overlay on / off | Alt+0 |
| lock overlay | Lock / unlock the overlay | not set |

A command whose job has no key in EDSMT is left out of the file, and EDSMT
says which ones. AltGr is pressed as Left Ctrl and Left Alt together, which
is what Windows hands EDSMT for AltGr.

## What VoiceAttack's documentation confirms

- A profile is exported to, and imported from, a file ending `.vap`
  ([how-to][howto]).
- An export can be expanded XML: the export window's *Save as type*
  offers "VoiceAttack Profile Expanded as XML (*.vap)" ([forum, topic
  3830][t3830]). The other form is compressed binary (VoiceAttack's help,
  quoted in [forum, topic 3793][t3793]).
- The XML form can be read in any text editor ([forum, topic 1802][t1802],
  a VoiceAttack moderator, 3 March 2018).
- There is no published description of the `.vap` format: asked for one,
  the forum's administrator answered that there is no format document and
  suggested building a profile and looking at what VoiceAttack writes
  ([forum, topic 1802][t1802], 3 March 2018).
- Three flags lock a profile. `CR` stops commands being added and `BE`
  stops the profile being exported as editable XML; both are profile flags
  and sit right above the closing `</Profile>` tag. `CL` locks a command
  and is in every command: locking them all is a find and replace of
  `<CL>0</CL>` with `<CL>1</CL>` ([forum, topic 3793][t3793], a VoiceAttack
  moderator, 16 March 2021). A profile handed out as compressed binary with
  `BE` set cannot be turned back (VoiceAttack's help, quoted in the same
  post).
- A key press is held for the number of seconds set in the action, then
  let go ([help][help], the key press screen).
- Changing a `.vap` by hand and importing it is at your own risk
  ([forum, topic 3830][t3830]).
- Key presses go out in one of two input modes, Standard or DirectX
  ([how-to][howto]).

## What EDSMT writes

Expanded XML only - the form VoiceAttack says is readable - in UTF-8:
a `Profile` named Radio Raxxla EDSMT, one `Command` for each phrase above
with the phrase as its `CommandString`, and one key-press action in each
that holds the keys together for 0.1 s and lets go. The keys are Windows
virtual-key codes, modifiers first (Left Ctrl 162, Left Alt 164, Left
Shift 160, Left Win 91), then the key itself. Each command's `CL`, and `CR`
and `BE` right above the closing tag, are 0, so the profile can be edited
and exported again. Nothing in it names any other product.

## What is not confirmed

These have not been checked against VoiceAttack's own documentation,
because there is none for the format, nor against an import into
VoiceAttack in this build:

- Every element name and how they nest below `Profile`: `Commands`,
  `Command`, `CommandString`, `ActionSequence`, `CommandAction`,
  `ActionType` with the value `PressKey`, `Duration`, `KeyCodes` holding
  `unsignedShort` values, `Enabled`, `UseSpokenPhrase`, `Category` and the
  rest. None of them is in VoiceAttack's documentation; they are meant to
  match a profile VoiceAttack exports as expanded XML, and have not been
  compared with one here.
- That `KeyCodes` holds Windows virtual-key codes.
- Where `CL` sits among a command's other elements: the moderator's post
  says only that every command has one.
- That a key VoiceAttack presses reaches EDSMT's keys in both input modes.
- Which versions of VoiceAttack accept the file.

To check a profile by hand after importing it: open the profile in
VoiceAttack, edit a command, and look at its key press - the keys shown
should be the ones on EDSMT's Keys page.

[howto]: https://voiceattack.com/howto.aspx
[help]: https://voiceattack.com/VoiceAttackHelp.pdf
[t1802]: https://forum.voiceattack.com/smf/index.php?topic=1802.0
[t3793]: https://forum.voiceattack.com/smf/index.php?topic=3793.0
[t3830]: https://forum.voiceattack.com/smf/index.php?topic=3830.0
