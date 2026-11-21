# EventHub

An event discovery and ticketing app built for the **Cloud Computing special assignment**.
Participants browse events, register, and keep their tickets. Organisers create events, see
attendees and analytics, and send reminders.

This is **phase 1: it runs completely on your laptop**. The backend is written as AWS Lambda
handlers, so phase 2 (moving to AWS) swaps configuration, not code.

| Layer | Local (now) | AWS (phase 2) |
|---|---|---|
| Frontend | React + Vite dev server | Amazon S3 static website (+ CloudFront) |
| API | `local_server.py` calls the Lambda handler | Amazon API Gateway, AWS Lambda (Python) |
| Auth | Own JWT login (`auth.py`) | Amazon Cognito user pool |
| Database | JSON file (`backend/data/db.json`) | Amazon DynamoDB |
| Notifications | Saved to an outbox shown in the dashboard | Amazon SNS |
| Reminders | "Send due reminders" button | Amazon EventBridge schedule triggers Lambda |
| Logs | Printed in the terminal | Amazon CloudWatch |

## Requirements

- Python 3.10 or newer (no packages needed to run the app)
- Node.js 18 or newer

## Run it (two terminals)

**Terminal 1: backend** (http://localhost:8000)

```bash
cd backend
python local_server.py          # on Windows you can also use: py local_server.py
```

**Terminal 2: frontend** (http://localhost:5173)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

### Demo accounts

| Role | Email | Password |
|---|---|---|
| Organiser (admin) | `admin@eventhub.test` | `Admin@123` |
| Participant | `user@eventhub.test` | `User@1234` |

The sign-in page also has "Try as participant" and "Try as organiser" buttons.

The first start creates 12 demo events with registrations. To wipe everything and start fresh:

```bash
python local_server.py --reset
```

## Run the tests

```bash
cd backend
pip install -r requirements.txt     # only needed for the DynamoDB tests (moto, boto3)
python -m unittest discover -s tests -v
```

30 tests: 15 API tests against the local store, and the same 15 against DynamoDB (simulated
in memory by moto). If the DynamoDB tests pass, the AWS storage code works.

## What you can do in the app

- **Everyone**: search and filter events, see seats left, view event details.
- **Participants**: sign up, register (a seat is reserved atomically, so nobody can book the
  last seat twice), get a ticket code, cancel, view *My tickets*.
- **Organisers**: dashboard with stats and charts, create/edit/delete events, attendee list per
  event, notification outbox, and a button that sends reminders for events starting in 24 hours.

## Project structure

```
eventhub/
├── backend/
│   ├── local_server.py            run the API locally (wraps the Lambda handler)
│   ├── eventhub/
│   │   ├── handlers.py            all routes + lambda_handler()  → AWS Lambda entry point
│   │   ├── reminders.py           lambda_handler() for the EventBridge schedule
│   │   ├── db.py                  LocalStore (JSON) and DynamoStore (DynamoDB), same interface
│   │   ├── auth.py                password hashing + JWT (replaced by Cognito on AWS)
│   │   ├── notify.py              outbox file locally, Amazon SNS on AWS
│   │   ├── config.py              all settings come from environment variables
│   │   └── seed.py                demo data
│   ├── scripts/create_dynamodb_tables.py
│   └── tests/
└── frontend/
    └── src/
        ├── api.js                 API client (base URL from VITE_API_URL)
        ├── auth.jsx               login state (the file that changes for Cognito)
        ├── pages/                 Home, EventDetail, AuthPage, MyTickets, Admin
        └── components/            Poster, EventCard, Navbar, Modal, ...
```

## API

All paths are relative to the API base URL. `Auth` means `Authorization: Bearer <token>`.

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/health` | public | Status and active modes |
| POST | `/auth/signup`, `/auth/login` | public | Local auth only |
| GET | `/auth/me` | signed in | Current user |
| GET | `/events` | public | List (`q`, `category`, `scope=upcoming\|past\|all`) |
| GET | `/events/{id}` | public | Detail, plus the caller's registration |
| POST | `/events` | admin | Create |
| PUT / DELETE | `/events/{id}` | admin | Update / delete (delete notifies attendees) |
| POST | `/events/{id}/register` | signed in | Reserve a seat, create ticket, send confirmation |
| DELETE | `/registrations/{id}` | owner or admin | Cancel and release the seat |
| GET | `/registrations/me` | signed in | My tickets |
| GET | `/events/{id}/registrations` | admin | Attendee list |
| GET | `/admin/stats` | admin | Dashboard numbers |
| POST | `/admin/reminders/run` | admin | Send due reminders now |
| GET | `/admin/notifications` | admin | Notification outbox |

## Configuration (environment variables)

Nothing needs to be set locally. On AWS these go on the Lambda function.

| Variable | Local default | AWS value |
|---|---|---|
| `STORAGE` | `local` | `dynamodb` |
| `AUTH_MODE` | `local` | `cognito` |
| `NOTIFY_MODE` | `local` | `sns` |
| `SNS_TOPIC_ARN` | – | ARN of your topic |
| `EVENTS_TABLE`, `REGISTRATIONS_TABLE`, `USERS_TABLE` | `EventHub…` | table names |
| `JWT_SECRET` | dev value | not used with Cognito |
| `VITE_API_URL` (frontend build) | `/api` | API Gateway invoke URL |

## Troubleshooting

- **"Cannot reach the server"** in the browser: the backend is not running. Start Terminal 1.
- **Port already in use**: `python local_server.py --port 9000`, then change the proxy target in `frontend/vite.config.js`.
- **`python` not found on Windows**: use `py local_server.py`.
- **Fonts look different offline**: the fonts load from Google Fonts. The app still works without them.
