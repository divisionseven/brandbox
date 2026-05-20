# Google / Gmail Setup Guide

This guide walks through everything needed to use brandbox with Gmail personal accounts or Google Workspace (business) accounts.

---

## Supported account types

| Account type                        | Supported | Notes                                    |
| ----------------------------------- | --------- | ---------------------------------------- |
| Gmail (personal)                    | ✅ Yes     | Full support via People API              |
| Google Workspace (business)         | ✅ Yes     | Full support via People API              |
| Google Workspace (admin-restricted) | ⚠️ Partial | Depends on your admin's OAuth app policy |

> **Gmail added to Outlook:** If you have a Gmail account connected inside Outlook, brandbox cannot set logos for it via the Microsoft provider — Outlook manages those contacts locally, outside of Exchange. Add it separately using `brandbox --add-account --provider google` to get logos for Gmail senders.

---

## Where logos appear

Once brandbox sets a contact photo via the Google People API, it propagates automatically to every Google client connected to that account.

| Client            | Logos shown | Notes                               |
| ----------------- | ----------- | ----------------------------------- |
| Gmail (web)       | ✅ Yes       | Hard-refresh the page after running |
| Gmail for iOS     | ✅ Yes       | May take a few minutes to sync      |
| Gmail for Android | ✅ Yes       | May take a few minutes to sync      |
| Google Contacts   | ✅ Yes       | Logos appear here immediately       |
| Google Meet       | ✅ Bonus     | Contact photos appear in Meet       |
| Google Chat       | ✅ Bonus     | Contact photos appear in Chat       |

---

## Step 1 — Create a Google Cloud project

brandbox uses the Google People API to read and update contact photos. This requires a free Google Cloud project with OAuth 2.0 credentials — no billing or paid plan is needed.

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Sign in with any Google account (this will be the owner of the project — it doesn't have to be the Gmail account you're setting up logos for)
3. Click **Select a project** in the top bar → **New Project**
4. Name it `brandbox` and click **Create**
5. Make sure the new project is selected in the top bar before continuing

---

## Step 2 — Enable the required APIs

1. In the left sidebar, go to **APIs & Services → Library**
2. Search for **People API** and click **Enable**
3. Go back to the library, search for **Gmail API** and click **Enable**

> **Gmail API is optional** — it's only needed if you plan to use `--scan-inbox`. If you only want to set logos on existing contacts, you can skip enabling the Gmail API. If you add it later, you'll need to re-authenticate your account to grant the new scope.

---

## Step 3 — Configure the OAuth consent screen

Before creating credentials, Google requires you to configure an OAuth consent screen. This is the screen users see when authorising the app.

1. In the left sidebar, go to **APIs & Services → OAuth consent screen**
2. Select **External** as the user type and click **Create**
3. Fill in the required fields:
   - **App name:** `brandbox`
   - **User support email:** your email address
   - **Developer contact information:** your email address
4. Click **Save and Continue** through the **Scopes** and **Test users** pages — you don't need to change anything on those pages
5. On the **Summary** page, click **Back to Dashboard**

> **Publishing status:** Google will set your app to "Testing" mode by default. In Testing mode, only Google accounts explicitly added as test users can sign in. Since you're the only user, this is fine — you can add yourself as a test user, or publish the app (which just removes the test user restriction for a personal app like this).
>
> To add yourself as a test user: go to **OAuth consent screen → Test users → Add users** and enter your Gmail address.

---

## Step 4 — Create OAuth credentials

1. In the left sidebar, go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. Set **Application type** to **Desktop app**
4. Set the **Name** to `brandbox`
5. Click **Create**
6. In the dialog that appears, click **Download JSON**
7. Save the downloaded file somewhere permanent and secure — for example:

```bash
mkdir -p ~/.config/brandbox
mv ~/Downloads/client_secret_*.json ~/.config/brandbox/google_credentials.json
```

> **Keep this file private.** It contains your OAuth client secret. Don't commit it to version control or share it. It's not a token — it's more like a key that's used to generate tokens — but it should still be treated carefully.

---

## Step 5 — Set the credentials path

### Standard approach

Add the following to your `~/.zshrc` or `~/.zshenv`:

```bash
export BRANDBOX_GOOGLE_CREDENTIALS="$HOME/.config/brandbox/google_credentials.json"
```

### macOS Keychain approach

Since this is a file path rather than a secret value, storing it in Keychain is less critical than for the Microsoft client ID. However, if you prefer to keep all brandbox config out of your dotfiles entirely, you can store the path in Keychain:

```bash
security add-generic-password -a "$USER" -s "brandbox-google-credentials" -w "$HOME/.config/brandbox/google_credentials.json"
```

Then in `~/.zshrc` or `~/.zshenv`:

```zsh
export BRANDBOX_GOOGLE_CREDENTIALS=$(security find-generic-password -a "$USER" -s "brandbox-google-credentials" -w)
```

---

## Step 6 — Authenticate your account

```bash
brandbox --add-account --provider google
```

A browser window will open automatically with Google's sign-in page. Sign in with the Gmail account you want to add logos for.

**"This app isn't verified" warning**

Google shows this warning for all OAuth apps that haven't gone through Google's formal verification process. Since this is your own private app registration, this is expected and safe to proceed through:

1. Click **Advanced**
2. Click **Go to brandbox (unsafe)**
3. Review the permissions and click **Continue**

This warning appears because Google requires a formal review for apps that request sensitive scopes and intend to be distributed publicly. For personal use, the unverified status has no practical impact.

If you have multiple Gmail or Workspace accounts, repeat `--add-account` for each one.

---

## Step 7 — Run

```bash
brandbox --run
```

### Using --scan-inbox with Google

The `--scan-inbox` flag works differently for Google than for Microsoft. Rather than scanning individual Gmail messages, brandbox uses Google's `otherContacts` endpoint — a list of people you've exchanged email with but haven't explicitly added to your contacts. This is more efficient (no N+1 API calls) and covers your full interaction history rather than just recent messages.

```bash
brandbox --run --scan-inbox
```

As with all providers, a contact is only created if a logo can be found for that sender's domain first. Senders with no logo are silently skipped.

> **Fewer results than expected:** Google's `otherContacts` endpoint only includes people you've *directly exchanged* email with (sent or received), not every address that has ever appeared in your inbox. Newsletters, mailing lists, and automated senders you've never replied to may not appear. This is a Google API limitation.

---

## Multiple accounts

brandbox supports any number of Google accounts. Run `--add-account` once per account:

```bash
brandbox --add-account --provider google   # personal Gmail
brandbox --add-account --provider google   # work Workspace account
```

All accounts — including any Microsoft accounts you've also added — are processed together in a single `brandbox --run`.

---

## Google Workspace considerations

If you're using a Google Workspace account managed by an organisation:

- Your Workspace admin may have restricted which third-party OAuth apps users can authorise. If you see an error saying the app is blocked by your organisation's policy, ask your admin to allow the app, or use the admin console to mark the brandbox OAuth client ID as trusted.
- The `Contacts.ReadWrite` scope in the People API only grants access to your **personal contacts** — not the organisation's shared directory (Domain Shared Contacts). brandbox cannot set photos on contacts in the shared directory unless you're a Workspace admin with domain-wide delegation configured.
- For most individual Workspace users, personal contacts are sufficient — these are the contacts that appear in Gmail's autocomplete and contact list.

---

## Troubleshooting

**"This app isn't verified" on every sign-in**
This is normal for personal OAuth apps. Click **Advanced → Go to brandbox (unsafe)** each time, or publish your app in the Google Cloud Console to remove the warning (no review required for personal-use apps in Testing mode with only yourself as a test user).

**"Access blocked: brandbox has not completed the Google verification process"**
Your account is not listed as a test user. Go to **APIs & Services → OAuth consent screen → Test users** and add your Gmail address.

**Logos not appearing after running**
- Gmail (web): hard-refresh the page (`⌘+Shift+R` / `Ctrl+Shift+R`)
- Gmail mobile: close and reopen the app; may take a few minutes
- Google Contacts: logos should appear here immediately — if not, check that the run completed without errors

**Token expired or "re-authenticate" error**
Run `brandbox --add-account --provider google` again for the affected account.

**--scan-inbox not finding expected senders**
Google's `otherContacts` only includes people you've directly exchanged email with. Mass-mailed senders, newsletters, and addresses you've never replied to may not appear. This is a limitation of the Google People API.

**Workspace admin blocked the app**
Ask your Google Workspace admin to allow the app via **Admin Console → Security → API controls → App access control**, or have them add your OAuth client ID to the trusted apps list.
