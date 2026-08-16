---
name: coding-conventions
description: Coding rules and Django layered architecture conventions for the Slack bot backend — file structure order, one-class-per-file, no standalone functions, serializer validation, service/manager layering. Use whenever writing or modifying Python/Django code in this project (models, views, serializers, services, managers, utils).
---

# Coding Rules

Follow these rules for all code you write or modify.

## Code Structure

* Every file must follow this order:

  1. File-level docstring
  2. Imports
  3. One main class
  4. Exports
* One class per file.
* Never write standalone functions. All functions must belong to a class.
* Each function should perform one clearly defined task.
* Use descriptive names for files, classes, methods, and variables.
* Do not add inline comments.
* Add a short docstring at the beginning of every file describing its purpose.

## Django Structure

```text
/app
├── models/        # Models
├── managers/      # Database operations and queries
├── migrations/    # Django migrations
├── services/      # Business logic
├── views/         # API request/response handling
├── serializers/   # Request validation and serialization
├── utils/         # Generic reusable helpers
├── urls.py
├── apps.py
└── admin.py
```

Services may be split into domain-specific subdirectories when needed.

## Layer Responsibilities

* **Models:** Define database models.
* **Managers:** Handle database queries and operations.
* **Serializers:** Validate API input and handle create/update operations.
* **Services:** Contain business logic and orchestrate workflows.
* **Views:** Handle HTTP requests/responses and delegate to services.
* **Utils:** Contain generic reusable helper logic.

## API Rules

* Validate every API request using a serializer.
* Never trust raw request data.
* All create and update operations must go through serializers.
* Database operations other than serializer-based create/update must go through model managers.
* Do not put business logic or database queries directly in views.
* Implement views using DRF ViewSets rather than plain function-based views or bare APIView classes.

## Prefer Existing Packages

* Before writing manual code for a piece of functionality, check whether an existing, well-maintained Python package already provides it, and use that instead.

## Naming & Organization

* Use descriptive, explicit names; avoid unnecessary abbreviations.
* Keep files focused on a single responsibility.
* Use proper file names that describe their purpose.
* Do not create generic files such as `helper.py`, `common.py`, or `misc.py` unless genuinely justified.
* Keep business-specific services organized into appropriate subdirectories.

## Default Request Flow

```text
Request
  → View
  → Serializer
  → Service
  → Manager / Serializer
  → Database
  → Response Serializer
  → View
  → Response
```

Follow these conventions for all new code and when modifying existing code.
