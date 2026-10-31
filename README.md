Survivors Network

An independent, survivor-controlled information and resource network.

Project Overview

Survivors Network is designed to provide individuals with a comfortable, accessible environment for organizing private information and finding practical resources.

The project follows a modular development approach, separating local storage, encryption, research, resource discovery, network coordination, and application presentation.

The central design objective is individual control: survivors should not have to entrust their personal records to a central administrator or public database.

GitHub is used to distribute the software, documentation, and public-facing project information. It is not intended to serve as a repository for private survivor information.

Design Principles

* Individual control over personal information.
* Local-first operation.
* Encrypted personal records.
* Independent and modular software components.
* Explicit permission for information sharing.
* Redundant development and independently verifiable operations.
* Accessible presentation designed to reduce unnecessary cognitive stress.

Current Application

The initial local release includes:

* Encrypted personal records.
* Local SQLite storage.
* Argon2id password-based key derivation.
* AES-256-GCM authenticated encryption.
* Resource directory.
* Local application diagnostics.
* Privacy and safety information.

Installation

Requirements

* Python 3.10 or newer.
* pip.
* A computer with local storage controlled by the user.

Download

Download the repository ZIP from GitHub or clone the repository:

git clone YOUR_REPOSITORY_URL

Enter the project directory:

cd Survivors-Network

Create a Python environment

python -m venv .venv

Windows:

.venv\Scripts\activate

macOS/Linux:

source .venv/bin/activate

Install dependencies

pip install -r requirements.txt

Start the application

streamlit run survivors_network.py

The application will display a local address in the terminal.

Open that address in a browser on the same computer.

Local Data Storage

By default, the encrypted database is stored in:

~/.survivors_network/

The application stores:

* survivors_vault.sqlite3
* vault.salt

Keep these files together when creating a backup.

The salt is not a secret, but it is required to derive the same encryption key later. Losing it can make the encrypted records unrecoverable.

The user’s passphrase is not stored in the database.

Docker Installation

Docker is optional.

Build and start:

docker compose up --build -d

Open:

[(https://github.com/mamaofthree579-ship-it/SurvivorsNetwork/)]

Stop the application:

docker compose down

The local vault is retained in the local_vault directory.

GitHub Pages

The dashboard.html file can be published through GitHub Pages.

It provides a public project introduction and download information. It does not run the private application or access local survivor records.

Planned Development

The architecture is intended to expand through independently maintained modules:

1. Local storage and encryption.
2. Independent node identity and registration.
3. Peer discovery and authenticated communication.
4. Independent crawler execution.
5. Resource verification and source evaluation.
6. Encrypted mailbox and voluntary information exchange.
7. Synchronization and conflict resolution.
8. Research governance and audit trails.
9. Redundant storage and recovery mechanisms.

These capabilities must be implemented and tested before being represented as operational.

Security Limitations

The initial release provides encryption at rest, not complete protection against every form of device compromise.

It cannot guarantee protection against malware, keyloggers, screen capture, operating-system compromise, or access to an unlocked computer.

Deleting a record from SQLite does not guarantee forensic erasure from storage media or backups.

Do not enter highly sensitive information on a device you believe may be monitored.

Project Philosophy

Survivors Network is being developed as a modular, independently operated system rather than a conventional centralized database.

The long-term objective is to give individuals meaningful control over their information while making practical support resources easier to access.

Individual control, privacy, accessibility, and responsible information sharing are foundational project principles.
