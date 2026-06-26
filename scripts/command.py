#!/usr/bin/env python3
"""
CLI tool for admin operations: user management and project deletion.

Commands:
    create-user      Create a new user (password hidden)
    update-password  Update a user's password by email (password hidden)
    delete-projects  Soft-delete projects (all, or from a given date)
    prune-projects   Physically delete all soft-deleted projects
"""

import argparse
import asyncio
import getpass
import sys
from datetime import datetime

from app.database.users_repository import UsersRepository
from app.database.projects_repository import ProjectsRepository


# ---------------------------------------------------------------------------
# create-user
# ---------------------------------------------------------------------------
async def cmd_create_user(args: argparse.Namespace) -> None:
    """Create a new user interactively."""
    print("=== Create New User ===")
    email = input("Email: ").strip()
    if not email:
        print("❌ Email is required.", file=sys.stderr)
        sys.exit(1)

    name = input("Name: ").strip()
    if not name:
        print("❌ Name is required.", file=sys.stderr)
        sys.exit(1)

    password = getpass.getpass("Password: ")
    if not password:
        print("❌ Password cannot be empty.", file=sys.stderr)
        sys.exit(1)

    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("❌ Passwords do not match.", file=sys.stderr)
        sys.exit(1)

    role = input("Role [user]: ").strip() or "user"

    repo = UsersRepository()
    user_id = await repo.create_user(email=email, password=password, name=name, role=role)

    if user_id:
        print(f"✅ User created successfully! ID: {user_id}")
    else:
        print("❌ Failed to create user (email may already exist).", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# update-password
# ---------------------------------------------------------------------------
async def cmd_update_password(args: argparse.Namespace) -> None:
    """Update a user's password by email."""
    print("=== Update User Password ===")
    email = input("Email: ").strip()
    if not email:
        print("❌ Email is required.", file=sys.stderr)
        sys.exit(1)

    repo = UsersRepository()
    user = await repo.get_user_by_email(email)

    if user is None:
        print(f"❌ No user found with email: {email}", file=sys.stderr)
        sys.exit(1)

    print(f"Found user: {user.get('name')} ({user.get('email')})")

    new_password = getpass.getpass("New password: ")
    if not new_password:
        print("❌ Password cannot be empty.", file=sys.stderr)
        sys.exit(1)

    confirm = getpass.getpass("Confirm new password: ")
    if new_password != confirm:
        print("❌ Passwords do not match.", file=sys.stderr)
        sys.exit(1)

    user_id = str(user["_id"])
    success = await repo.update_password(user_id=user_id, new_password=new_password)

    if success:
        print(f"✅ Password updated successfully for {email}!")
    else:
        print("❌ Failed to update password.", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# delete-projects
# ---------------------------------------------------------------------------
async def cmd_delete_projects(args: argparse.Namespace) -> None:
    """Soft-delete projects (all, or from a specific date)."""
    if args.all:
        print("⚠️  This will soft-delete ALL projects!")
        confirm = input("Type 'DELETE' to confirm: ")
        if confirm != "DELETE":
            print("❌ Aborted.")
            sys.exit(0)
        from_date = None
    else:
        from_date = args.from_date
        if from_date:
            # Validate date format
            try:
                datetime.strptime(from_date, "%Y-%m-%d")
            except ValueError:
                print(f"❌ Invalid date format: {from_date}. Use YYYY-MM-DD.", file=sys.stderr)
                sys.exit(1)
            print(f"⚠️  This will soft-delete projects with estimated_published_at >= {from_date}!")
            confirm = input("Type 'DELETE' to confirm: ")
            if confirm != "DELETE":
                print("❌ Aborted.")
                sys.exit(0)
        else:
            print("❌ You must specify --all or --from-date YYYY-MM-DD.", file=sys.stderr)
            sys.exit(1)

    repo = ProjectsRepository()
    count = await repo.delete_projects(from_date=from_date if not args.all else None)

    print(f"✅ {count} project(s) soft-deleted.")


# ---------------------------------------------------------------------------
# prune-projects
# ---------------------------------------------------------------------------
async def cmd_prune_projects(args: argparse.Namespace) -> None:
    """Physically delete all soft-deleted projects."""
    print("⚠️  This will PERMANENTLY DELETE all soft-deleted projects!")
    print("   (projects with a deleted_at timestamp)")
    confirm = input("Type 'PRUNE' to confirm: ")
    if confirm != "PRUNE":
        print("❌ Aborted.")
        sys.exit(0)

    repo = ProjectsRepository()
    count = await repo.prune_projects()
    print(f"✅ {count} project(s) permanently deleted.")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Admin CLI for user and project management."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # create-user
    sub.add_parser("create-user", help="Create a new user")

    # update-password
    sub.add_parser("update-password", help="Update a user's password by email")

    # delete-projects
    dp = sub.add_parser("delete-projects", help="Soft-delete projects")
    dp_group = dp.add_mutually_exclusive_group(required=True)
    dp_group.add_argument(
        "--all", action="store_true", help="Delete all projects"
    )
    dp_group.add_argument(
        "--from-date", type=str, metavar="YYYY-MM-DD",
        help="Delete projects published on or after this date"
    )

    # prune-projects
    sub.add_parser("prune-projects", help="Permanently delete all soft-deleted projects")

    args = parser.parse_args()

    # Route to the correct async handler
    match args.command:
        case "create-user":
            asyncio.run(cmd_create_user(args))
        case "update-password":
            asyncio.run(cmd_update_password(args))
        case "delete-projects":
            asyncio.run(cmd_delete_projects(args))
        case "prune-projects":
            asyncio.run(cmd_prune_projects(args))


if __name__ == "__main__":
    main()