# WhatsApp Provider Integration

A FastAPI-based WhatsApp messaging service built with a provider-based architecture that supports **multiple WhatsApp Business Solution Providers (BSPs)** such as **Emovur**, **Meta WhatsApp Cloud API**, or any other BSP by implementing a new provider.

The project is designed to be modular, scalable, and easily integrated into larger backend systems, making it simple to switch or extend WhatsApp providers without changing the application business logic.

---

## Features

- Provider-agnostic architecture
- Supports multiple WhatsApp BSPs (Emovur, Meta Cloud API, or custom providers)
- Easy integration of new BSPs through the provider interface
- Send WhatsApp template messages
- Fetch and synchronize approved templates
- Webhook support for incoming messages and delivery events
- REST APIs built with FastAPI
- SQLAlchemy database integration
- Environment-based configuration
- Unit tests included

---

## Provider Architecture

```
                    API Request
                         │
                         ▼
                 Provider Factory
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
     Emovur BSP     Meta Cloud API   Custom BSP
          │              │              │
          └──────────────┴──────────────┘
                         │
                         ▼
               WhatsApp Business API
```

The application follows a provider abstraction pattern. Any WhatsApp Business Solution Provider (BSP) can be integrated by implementing the provider interface and registering it with the Provider Factory. This allows the application to switch providers without modifying the core business logic.
