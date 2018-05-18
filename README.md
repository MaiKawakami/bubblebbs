# bubblebbs

[![Build
Status](https://travis-ci.org/lily-fyi/bubblebbs.svg?branch=master)](https://travis-ci.org/lily-fyi/bubblebbs)

Text BBS/message board.

This project is in alpha. It is currently unversioned and very messy.

## General technical

Before you start:

  * Make sure you're using latest Docker and docker-compose, install according to
    Docker community instructions, don't install via your distribution's repo (it's
    probably way out-of-date!).
  * Docker will look for `.env-file`. So you need to `touch .env-file`. This
    includes setting up your Google Recaptcha info. Here are possible
    `.env-file` settings:
    * `BBBS_RECAPTCHA_SITE_KEY`
    * `BBBS_RECAPTCHA_SECRET_KEY`
    * `BBBS_SECRET_KEY`

There are multiple ways to run the app:

  * For production: Use Docker, `./launch-docker.sh prod`
  * To debug: either look at the "debugging without docker" section in this
    `README` or use `./launch-docker.sh debug`
  * Running tests: if you followed the "debugging without docker" section you
    can simply run `pytest` in the project root. Otherwise use
    `./launch-docker.sh pytest`.

Admins login at `/admin` with the default username `admin` and default password `admin`.

## Debugging without Docker

You can still fiddle around with `bubblebbs` like you would any ol' Python code:

  1. Create and activate a virtual environment
  1. `pip install -r requirements.txt`
  1. In Ubuntu I needed to `sudo apt install libssl-dev` (this is for `scrypt`)
  1. `python3 -m bubblebbs.runserver`
  1. http://localhost:8080/

You can run tests with `pytest` in the project root.
