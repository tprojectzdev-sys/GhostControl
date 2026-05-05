# Siri Shortcuts setup

Three iPhone-side ingredients:

1. **One parameterized "Send PC Command" shortcut.** All other shortcuts
   call this one. Update the token in one place.
2. **Per-phrase shortcuts** that call the parameterized one with a fixed
   command name. These are what Siri actually triggers.
3. **A status shortcut** that just hits `/v1/status` and reads the result
   aloud.

This guide assumes the relay is at
`https://axon-relay-production.up.railway.app` (replace with yours).

---

## 1. Create the parameterized shortcut

Open the Shortcuts app → **+** → name it `Send PC Command`.

### Inputs

In **(i) → Show More** under the shortcut name, set:

- **Receive**: "Text" from "Share Sheet, What's On Screen, Quick Actions"
  (so other shortcuts can pass it data; doesn't matter much)

### Actions (in order)

1. **Get Variable** → tap *Variable* → **Shortcut Input** → rename to
   `cmd_input`. (This will be a JSON string passed by the caller.)
2. **Get Current Date** → set Format → **Custom**: `Unix Time`. Save into
   `ts`.
3. **Generate UUID** → save into `req_id`.
4. **Dictionary** → add three keys:
   - `id`  → variable `req_id`
   - `ts`  → variable `ts` (set type to Number)
   - `cmd` → variable `cmd_input` (set type to Text)
5. (Optional) **Dictionary** for `args`. If your `cmd_input` shortcuts
   need args, build a second dictionary and merge it in. For most Siri
   commands `args` is empty, so just add `args` → empty Dictionary.
6. **Get Contents of URL** →
   - **URL**: `https://axon-relay-production.up.railway.app/v1/cmd`
   - **Method**: POST
   - **Headers**:
     - `Authorization: Bearer <USER_API_KEY>` ← paste your token here
     - `Content-Type: application/json`
   - **Request Body**: JSON → from the dictionary you built in step 4
7. **Get Dictionary Value** → key path `status`, from the previous result.
   Save into `status_val`.
8. **If** `status_val` is `ok`:
   - **Show Notification** → "Sent ✅"  (or whatever you want).
   - Otherwise:
     - **Get Dictionary Value** → key `message` from the response.
     - **Show Notification** → that message.

### Test it

Run it once with input `power.lock`. Your PC should lock. The shortcut
should show "Sent ✅".

---

## 2. Per-phrase shortcuts

Each is just a one-line wrapper.

### "Lock my PC"

1. New shortcut, name `Lock my PC`.
2. **Run Shortcut** → choose `Send PC Command`, with input set to text
   `power.lock`.

That's it. Now say "Hey Siri, lock my PC". Done.

### "Sleep my PC"

Same, with input `power.sleep`.

### "Restart my PC" (with confirm)

1. New shortcut.
2. **Choose from Menu** → "Are you sure?" → options: "Yes" / "No".
3. **If** menu output is `Yes`:
   - **Run Shortcut** → `Send PC Command` with input `power.restart`.

### "Shut down my PC" (with confirm)

Same as restart but with input `power.shutdown`.

### "Wake my PC"

Just `power.wake`.

### "Open YouTube on my PC"

This one needs `args.url`. The simplest shape:

1. New shortcut.
2. **Text** action → paste this exact JSON, with the URL you want:
   ```json
   {"cmd":"url.open","url":"https://youtube.com"}
   ```
3. **Run Shortcut** → `Send PC Command`, but… we need to pass *both* the
   command name and the URL. To keep `Send PC Command` simple, build a
   second variant called `Send PC Command (with URL)`:
   - copies the parameterized shortcut, but the dictionary in step 4
     includes `args.url` from `Shortcut Input` parsed as a Dictionary.

Or, easier path: bake the JSON directly into a one-off shortcut without
going through `Send PC Command`. Just inline steps 2–8 of the
parameterized shortcut with hardcoded values.

### "Start work mode"

```json
{"cmd":"group.run","args":{"target":"work_morning"}}
```

Same as the URL example — easiest to inline.

---

## 3. Status shortcut

Useful for "Hey Siri, is my PC online?":

1. New shortcut, name `PC Status`.
2. **Get Contents of URL**:
   - URL: `https://<your-relay>.up.railway.app/v1/status`
   - Method: GET
   - Headers: `Authorization: Bearer <USER_API_KEY>`
3. **Get Dictionary Value** → key `pc.status.hostname`. Save into `host`.
4. **Get Dictionary Value** → key `pc.uptime_seconds`. Save into `uptime`.
5. **If** previous result is empty/null:
   - **Speak Text** → "PC is offline."
   - Otherwise:
     - **Speak Text** → "PC online for [uptime] seconds."

Tweak phrasing to taste.

---

## Tips

- **Keep secrets in one place.** Putting your `USER_API_KEY` in the
  parameterized shortcut means rotation is one edit, not N edits.
- **Lock the Shortcuts app behind Face ID** if anyone else has access to
  your phone. (Settings → Screen Time → Content & Privacy → App
  Limits.) The bearer token is stored as plaintext in the shortcut body.
- **Don't add Siri to destructive shortcuts without confirmation.**
  Shutdown/restart should always go through "Choose from Menu".
- **Use Focus Automations** to fire shortcuts on schedule. Example:
  enter "Sleep" focus → run `Lock my PC`. Or use NFC tags.
- **Apple Watch.** Once a shortcut shows up in your phone's library, it
  shows up on the Watch automatically. "Hey Siri" works from the Watch
  too.

---

## Why not just an app for everything?

You should have **both**. The native iOS app
([`ios/`](../ios)) is great for the "I want to see what's online and pick
an app to launch" case. Siri Shortcuts are great for "without taking my
phone out of my pocket". Both hit the same `/v1/cmd` with the same token.
