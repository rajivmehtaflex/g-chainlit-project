Here is a complete step-by-step guide for integrating a Custom UI with Chainlit, including password authentication and the session history sidebar.

---

## Architecture Overview

Chainlit has two integration paths for custom UI:

1. **Custom CSS/JS injection** — lightest approach, modifies the built-in UI
2. **`@chainlit/react-client`** — full custom React app using Chainlit's published hooks package

The session history sidebar requires **both** authentication AND a data layer to be active. This is enforced in the frontend: [1](#0-0) 

---

## Step 1: Install Chainlit (Backend)

```bash
pip install chainlit
```

Generate a secret key for JWT auth (required for password auth):

```bash
chainlit create-secret
``` [2](#0-1) 

Add the output to your `.env` file:

```
CHAINLIT_AUTH_SECRET="your-generated-secret-here"
```

---

## Step 2: Create the Chainlit Backend App

Create `app.py`:

```python
import os
from typing import Optional
import chainlit as cl

# Required for password auth JWT signing
os.environ["CHAINLIT_AUTH_SECRET"] = "your-secret-here"  # or load from .env

@cl.password_auth_callback
def auth_callback(username: str, password: str) -> Optional[cl.User]:
    # Replace with your real credential check (e.g., DB lookup)
    if (username, password) == ("admin", "admin"):
        return cl.User(identifier="admin", metadata={"role": "ADMIN"})
    return None

@cl.on_chat_start
async def on_start():
    user = cl.user_session.get("user")
    await cl.Message(f"Hello {user.identifier}!").send()

@cl.on_message
async def on_message(msg: cl.Message):
    await cl.Message(content=f"You said: {msg.content}").send()
```

The `@cl.password_auth_callback` decorator registers your function as the login handler. It receives `username` and `password` and must return a `cl.User` or `None`. [3](#0-2) 

The backend POST `/login` endpoint calls this callback: [4](#0-3) 

---

## Step 3: Enable a Data Layer (Required for Session Sidebar)

The thread history sidebar **only appears** when `dataPersistence` is `true` AND the user is logged in. You must register a data layer.

**Option A — SQLAlchemy (PostgreSQL/SQLite):**

```python
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer

@cl.data_layer
def data_layer():
    return SQLAlchemyDataLayer(conninfo="sqlite+aiosqlite:///./chainlit.db")
``` [5](#0-4) 

**Option B — Custom in-memory (for dev/testing):**

Subclass `cl_data.BaseDataLayer` and implement the required methods. [6](#0-5) 

---

## Step 4: Configure `.chainlit/config.toml`

Run `chainlit init` to generate the config, then edit it:

```toml
[project]
# Enable session persistence
enable_telemetry = false

[UI]
name = "My AI Assistant"
default_sidebar_state = "open"   # "open", "closed", or "hidden"
layout = "default"
```

Key `default_sidebar_state` values: [7](#0-6) 

---

## Step 5: Option A — Custom CSS/JS Only (Simplest)

Place a CSS file in `public/custom.css` and reference it in `config.toml`:

```toml
[UI]
custom_css = "/public/custom.css"
``` [8](#0-7) 

Run the app:

```bash
chainlit run app.py
```

---

## Step 6: Option B — Full Custom React UI with `@chainlit/react-client`

### 6a. Install the npm package

```bash
npm install @chainlit/react-client recoil
``` [9](#0-8) 

### 6b. Bootstrap your React app entry point

```tsx
// main.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { RecoilRoot } from 'recoil';
import { ChainlitAPI, ChainlitContext } from '@chainlit/react-client';

const apiClient = new ChainlitAPI('http://localhost:8000', 'webapp');

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ChainlitContext.Provider value={apiClient}>
      <RecoilRoot>
        <MyApp />
      </RecoilRoot>
    </ChainlitContext.Provider>
  </React.StrictMode>
);
``` [10](#0-9) 

### 6c. Connect to the WebSocket session

```tsx
import { useChatSession, useChatMessages, useChatInteract, useChatData } from '@chainlit/react-client';
import { useEffect } from 'react';

function ChatComponent() {
  const { connect, disconnect } = useChatSession();
  const { messages } = useChatMessages();
  const { sendMessage } = useChatInteract();
  const { connected, loading } = useChatData();

  useEffect(() => {
    connect({ userEnv: {} });
    return () => disconnect();
  }, []);

  const handleSend = () => {
    sendMessage({ output: 'Hello!', id: crypto.randomUUID() }, []);
  };

  return (
    <div>
      {messages.map(m => <p key={m.id}>{m.output}</p>)}
      <button onClick={handleSend} disabled={!connected || loading}>Send</button>
    </div>
  );
}
``` [11](#0-10) 

### 6d. Handle login in your custom UI

The `ChainlitAPI.passwordAuth()` method posts credentials to `/login`:

```tsx
import { useContext } from 'react';
import { ChainlitContext } from '@chainlit/react-client';

function LoginPage() {
  const apiClient = useContext(ChainlitContext);

  const handleLogin = async (username: string, password: string) => {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);
    const result = await apiClient.passwordAuth(formData);
    if (result?.success) {
      // Redirect to chat
    }
  };
  // ... render your form
}
``` [12](#0-11) 

### 6e. Point Chainlit to your custom build

Build your React app (`npm run build`) then set in `config.toml`:

```toml
[UI]
custom_build = "./public/build"
``` [13](#0-12) 

The server resolves this path relative to `APP_ROOT`: [14](#0-13) 

---

## Step 7: Run and Verify the Session Sidebar

```bash
chainlit run app.py --port 8000
```

The session history sidebar (`LeftSidebar`) appears **only when**:

- `config.dataPersistence` is `true` (data layer is registered)
- `data.requireLogin` is `true` (a password/OAuth/header auth callback is registered)
- `default_sidebar_state` is not `"hidden"` [15](#0-14) 

The sidebar shows thread history with search and new-chat controls: [16](#0-15) 

---

## Summary Checklist

| Requirement | What to do |
|---|---|
| Password login form | `@cl.password_auth_callback` + `CHAINLIT_AUTH_SECRET` env var |
| Session history sidebar | Register a `@cl.data_layer` (SQLAlchemy, DynamoDB, etc.) |
| Custom styling only | `custom_css` / `custom_js` in `config.toml` |
| Full custom React UI | `npm install @chainlit/react-client`, wrap in `ChainlitContext.Provider` + `RecoilRoot`, set `custom_build` |
| Sidebar default open | `default_sidebar_state = "open"` in `[UI]` config |

### Citations

**File:** frontend/src/pages/Page.tsx (L56-73)
```typescript
  const historyEnabled = config?.dataPersistence && data?.requireLogin;
  const sidebarHidden = config?.ui?.default_sidebar_state === 'hidden';

  return (
    <SidebarProvider
      defaultOpen={config?.ui.default_sidebar_state !== 'closed'}
    >
      {historyEnabled && !sidebarHidden ? (
        <>
          <LeftSidebar />
          <SidebarInset className="max-h-svh min-w-0">
            {mainContent}
          </SidebarInset>
        </>
      ) : (
        <div className="h-screen w-screen flex">{mainContent}</div>
      )}
    </SidebarProvider>
```

**File:** backend/chainlit/cli/__init__.py (L233-238)
```python
@cli.command("create-secret")
@click.argument("args", nargs=-1)
def chainlit_create_secret(args=None, **kwargs):
    print(
        f'Copy the following secret into your .env file. Once it is set, changing it will logout all users with active sessions.\nCHAINLIT_AUTH_SECRET="{random_secret()}"'
    )
```

**File:** backend/chainlit/callbacks.py (L65-83)
```python
def password_auth_callback(
    func: Callable[[str, str], Awaitable[Optional[User]]],
) -> Callable:
    """
    Framework agnostic decorator to authenticate the user.

    Args:
        func (Callable[[str, str], Awaitable[Optional[User]]]): The authentication callback to execute. Takes the email and password as parameters.

    Example:
        @cl.password_auth_callback
        async def password_auth_callback(username: str, password: str) -> Optional[User]:

    Returns:
        Callable[[str, str], Awaitable[Optional[User]]]: The decorated authentication callback.
    """

    config.code.password_auth_callback = wrap_user_function(func)
    return func
```

**File:** backend/chainlit/server.py (L213-216)
```python
    if config.ui.custom_build and os.path.exists(
        os.path.join(APP_ROOT, config.ui.custom_build)
    ):
        return os.path.join(APP_ROOT, config.ui.custom_build)
```

**File:** backend/chainlit/server.py (L534-552)
```python
@router.post("/login")
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """
    Login a user using the password auth callback.
    """
    if not config.code.password_auth_callback:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No auth_callback defined"
        )

    user = await config.code.password_auth_callback(
        form_data.username, form_data.password
    )

    return await _authenticate_user(request, user)
```

**File:** cypress/e2e/custom_data_layer/sql_alchemy.py (L15-19)
```python
@cl.data_layer
def data_layer():
    return SQLAlchemyDataLayer(
        conninfo="<your conninfo>", storage_provider=storage_client
    )
```

**File:** cypress/e2e/data_layer/main.py (L95-112)
```python
class TestDataLayer(cl_data.BaseDataLayer):
    async def get_user(self, identifier: str):
        if identifier == "user1":
            return cl.PersistedUser(id="user1_id", createdAt=now, identifier=identifier)
        elif identifier == "user2":
            return cl.PersistedUser(id="user2_id", createdAt=now, identifier=identifier)
        return None

    async def create_user(self, user: cl.User):
        if user.identifier == "user1":
            return cl.PersistedUser(
                id="user1_id", createdAt=now, identifier=user.identifier
            )
        elif user.identifier == "user2":
            return cl.PersistedUser(
                id="user2_id", createdAt=now, identifier=user.identifier
            )
        return None
```

**File:** backend/chainlit/config.py (L193-202)
```python
# Specify a CSS file that can be used to customize the user interface.
# The CSS file can be served from the public directory or via an external link.
# custom_css = "/public/test.css"

# Specify additional attributes for a custom CSS file
# custom_css_attributes = "media=\\\"print\\\""

# Specify a JavaScript file that can be used to customize the user interface.
# The JavaScript file can be served from the public directory.
# custom_js = "/public/test.js"
```

**File:** backend/chainlit/config.py (L232-235)
```python
# Specify a custom build directory for the frontend.
# This can be used to customize the frontend code.
# Be careful: If this is a relative path, it should not start with a slash.
# custom_build = "./public/build"
```

**File:** backend/chainlit/config.py (L350-358)
```python
class UISettings(BaseModel):
    name: str
    description: str = ""
    cot: Literal["hidden", "tool_call", "full"] = "full"
    default_theme: Optional[Literal["light", "dark"]] = "dark"
    language: Optional[str] = None
    layout: Optional[Literal["default", "wide"]] = "default"
    default_sidebar_state: Optional[Literal["open", "closed", "hidden"]] = "open"
    chat_settings_location: Optional[Literal["message_composer", "sidebar"]] = (
```

**File:** libs/react-client/package.json (L1-5)
```json
{
  "name": "@chainlit/react-client",
  "description": "Websocket client to connect to your chainlit app.",
  "version": "0.4.2",
  "scripts": {
```

**File:** libs/react-client/README.md (L14-35)
```markdown

```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { RecoilRoot } from 'recoil';

import { ChainlitAPI, ChainlitContext } from '@chainlit/react-client';

const CHAINLIT_SERVER_URL = 'http://localhost:8000';

const apiClient = new ChainlitAPI(CHAINLIT_SERVER_URL, 'webapp');

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <ChainlitContext.Provider value={apiClient}>
      <RecoilRoot>
        <MyApp />
      </RecoilRoot>
    </ChainlitContext.Provider>
  </React.StrictMode>
);
```
```

**File:** libs/react-client/README.md (L51-72)
```markdown
```jsx
import { useChatSession } from '@chainlit/react-client';

const ChatComponent = () => {
  const { connect, disconnect, chatProfile, setChatProfile } = useChatSession();

  // Connect to the WebSocket server
  useEffect(() => {
    connect({
      userEnv: {
        /* user environment variables */
      }
    });

    return () => {
      disconnect();
    };
  }, []);

  // Rest of your component logic
};
```
```

**File:** libs/react-client/src/api/index.tsx (L194-197)
```typescript
  async passwordAuth(data: FormData) {
    const res = await this.post(`/login`, data);
    return res.json();
  }
```

**File:** frontend/src/components/LeftSidebar/index.tsx (L10-28)
```typescript
export default function LeftSidebar({
  ...props
}: React.ComponentProps<typeof Sidebar>) {
  const navigate = useNavigate();
  return (
    <Sidebar {...props} className="border-none">
      <SidebarHeader className="py-3">
        <div className="flex items-center justify-between">
          <SidebarTrigger />
          <div className="flex items-center">
            <SearchChats />
            <NewChatButton navigate={navigate} />
          </div>
        </div>
      </SidebarHeader>
      <ThreadHistory />
      <SidebarRail />
    </Sidebar>
  );
```
