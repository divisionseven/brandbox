# Microsoft 365 Setup Guide

This guide walks through everything needed to use brandbox with Microsoft 365, Outlook.com, or any Microsoft-managed email account.

---

## Supported account types

| Account type                        | Supported | Notes                                   |
| ----------------------------------- | --------- | --------------------------------------- |
| Microsoft 365 work / school         | ✅ Yes     | Primary use case                        |
| Microsoft 365 Personal / Family     | ✅ Yes     | Uses the same Graph API                 |
| Outlook.com / Hotmail / Live (free) | ✅ Yes     | Fully supported                         |
| On-premises Exchange (non-hybrid)   | ❌ No      | Graph API cannot reach on-prem Exchange |
| On-premises Exchange (hybrid)       | ⚠️ Partial | Depends on your hybrid configuration    |

---

## Where logos appear

Once brandbox sets a contact photo via the Graph API, it propagates automatically to every Outlook client connected to that account. You don't need to run brandbox on each device.

| Client                        | Logos shown | Notes                                         |
| ----------------------------- | ----------- | --------------------------------------------- |
| Outlook for Mac               | ✅ Yes       | Restart Outlook after running                 |
| Outlook for Windows (new)     | ✅ Yes       | Restart Outlook after running                 |
| Outlook for Windows (classic) | ✅ Yes       | Restart Outlook after running; see note below |
| Outlook on the web (OWA)      | ✅ Yes       | Hard-refresh the page after running           |
| Outlook for iOS               | ✅ Yes       | May take a few minutes to sync                |
| Outlook for Android           | ✅ Yes       | May take a few minutes to sync                |
| Microsoft Teams               | ✅ Bonus     | Contact photos also appear in Teams           |

> **Classic Outlook for Windows:** The pre-2024 desktop app caches contact photos aggressively. If logos don't appear after restarting, go to **File → Account Settings → Account Settings**, remove and re-add your account. Alternatively, clear `%localappdata%\Microsoft\Outlook` and restart.

---

## Step 1 — Create an Azure App Registration

brandbox authenticates via the Microsoft Graph API using OAuth 2.0. This requires a free Azure App Registration — you don't need an Azure subscription.

1. Go to [portal.azure.com](https://portal.azure.com) and sign in with any Microsoft account
2. In the top search bar, search **"App registrations"** and select it
3. Click **New registration**
4. Fill in the form:
   - **Name:** `brandbox` (or anything you like — this is just a label)
   - **Supported account types:** select `Accounts in any organizational directory (Any Microsoft Entra ID tenant — Multitenant) and personal Microsoft accounts`
   - Leave **Redirect URI** blank for now
5. Click **Register**
6. On the overview page that loads, copy the **Application (client) ID** — you'll need this later

---

## Step 2 — Configure the authentication platform

1. In the left sidebar, click **Authentication**
2. Click **Add a platform**
3. Select **Mobile and desktop applications**
4. Check the box for: `https://login.microsoftonline.com/common/oauth2/nativeclient`
5. Click **Configure**, then **Save**

This tells Azure that brandbox is a native/desktop app and enables the device code flow used for authentication.

---

## Step 3 — Add API permissions

1. In the left sidebar, click **API permissions**
2. Click **Add a permission**
3. Select **Microsoft Graph**
4. Select **Delegated permissions**
5. Search for and add the following:
   - `Contacts.ReadWrite` — required to read and update contact photos
   - `Mail.Read` — only needed if you use `--scan-inbox`
6. Click **Add permissions**

You should now see both permissions listed with the status **Not granted for [your tenant]**. For personal Microsoft accounts, this is fine — consent is granted at login time. For managed work accounts, see the admin consent note below.

> **Admin consent for managed work accounts:** If your organisation restricts third-party app consent, you'll see "Admin approval required" during sign-in. In this case, send your IT admin the URL of your app registration in the Azure portal and ask them to click **Grant admin consent**. Alternatively, create the app registration under a personal Microsoft account or a tenant you control.

---

## Step 4 — Set your client ID

### Standard approach

Add the following to your `~/.zshrc` or `~/.zshenv`:

```bash
export BRANDBOX_CLIENT_ID="your-client-id-here"
```

On Windows, set `BRANDBOX_CLIENT_ID` as a user environment variable via **System Properties → Environment Variables**.

### macOS Keychain (recommended)

Rather than storing the value as plaintext in your shell config, you can keep it in the macOS Keychain. It never appears in your dotfiles or shell history.

**Store it once:**

```bash
security add-generic-password -a "$USER" -s "brandbox-client-id" -w "your-client-id-here"
```

**Retrieve it in `~/.zshrc` or `~/.zshenv`:**

```zsh
export BRANDBOX_CLIENT_ID=$(security find-generic-password -a "$USER" -s "brandbox-client-id" -w)
```

**To update it later:**

```bash
security delete-generic-password -a "$USER" -s "brandbox-client-id"
security add-generic-password -a "$USER" -s "brandbox-client-id" -w "your-new-client-id"
```

---

## Step 5 — Authenticate your account

```bash
brandbox --add-account --provider microsoft
```

A sign-in prompt will appear with a URL and a short code:

```
1. Open:  https://microsoft.com/devicelogin
2. Enter: XXXXXXXX
```

Open the URL in any browser, enter the code, and sign in with your Microsoft account. If you have multiple Microsoft 365 accounts, repeat this step for each one.

Tokens are stored locally and refresh automatically — you won't need to sign in again unless you explicitly remove an account or the token expires after an extended period of inactivity.

---

## Step 6 — Run

```bash
brandbox --run
```

To also create contacts for people who have emailed you but aren't in your contacts yet (logos are fetched first — if no logo is found the contact is not created):

```bash
brandbox --run --scan-inbox
```

To preview what would happen without making any changes:

```bash
brandbox --run --dry-run
```

---

## Multiple accounts

brandbox supports any number of Microsoft 365 accounts. Run `--add-account` once per account:

```bash
brandbox --add-account --provider microsoft   # account 1
brandbox --add-account --provider microsoft   # account 2
brandbox --add-account --provider microsoft   # account 3
```

All accounts are processed in a single `brandbox --run`.

---

## Troubleshooting

**"Admin approval required" during sign-in**
Your organisation has restricted third-party OAuth app consent. Ask your IT admin to grant consent for the app at the Azure portal, or use a personal Microsoft account for the app registration.

**"AADSTS70002: The client application must be marked as mobile"**
The platform was not configured correctly in Step 2. Go back to **Authentication** in your app registration, delete any existing Web platform entries, and add the **Mobile and desktop applications** platform with the `nativeclient` redirect URI.

**Logos not appearing after running**
- Mac: quit Outlook fully (`⌘Q`) and reopen
- Windows (new Outlook): close and reopen
- Windows (classic Outlook): close and reopen. If logos still don't show, remove and re-add your account via **File → Account Settings**, or clear `%localappdata%\Microsoft\Outlook`
- Web (OWA): hard-refresh the page (`Ctrl+Shift+R` or `⌘+Shift+R`)
- Mobile: close and reopen the app

**Token expired or "re-authenticate" error**
Run `brandbox --add-account --provider microsoft` again for the affected account. Tokens typically last 90 days of inactivity before expiring.

**Logos set but not appearing in Teams**
Teams syncs contact photos from Exchange, but may take up to 24 hours to reflect updates. If it doesn't appear after a day, sign out and back in to Teams.
