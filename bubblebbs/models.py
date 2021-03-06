# FIXME: primary key being avoided because you have to do
# some annoying copypaste code to get primary keys to show
import os
import re
import base64
import pathlib
import datetime
from typing import Tuple, Union
from urllib.parse import urlparse

import scrypt
import markdown
from mdx_bleach.extension import BleachExtension
from markdown.extensions.footnotes import FootnoteExtension
from markdown.extensions.smarty import SmartyExtension
from markdown.extensions.wikilinks import WikiLinkExtension
from jinja2 import Markup
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

from . import config


db = SQLAlchemy()


class TripMeta(db.Model):
    """Keeps track of tripcodes and postcount. Plus, if user
    proves they know unhashed version of tripcode they can
    set a Twitter URL, other links, a bio.

    """

    tripcode = db.Column(db.String(20), primary_key=True)
    post_count = db.Column(db.Integer, default=0, nullable=False)
    bio = db.Column(db.String(1000))
    bio_source = db.Column(db.String(400))


class FlaggedIps(db.Model):
    """Keeps track of which IPs have exhibited "bad behavior."

    """

    ip_address = db.Column(db.String(120), primary_key=True)


# FIXME: bad schema...
# TODO: tags
class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    ip_address = db.Column(db.String(120), nullable=False)
    locked = db.Column(db.Boolean(), default=False, nullable=False)
    permasage = db.Column(db.Boolean(), default=False, nullable=False)
    tripcode = db.Column(db.String(64))
    message = db.Column(db.String(2000), nullable=False, unique=True)
    reply_to = db.Column(db.Integer, db.ForeignKey('posts.id'))
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)
    bumptime = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)

    # FIXME: rename to_dict() and use summary output not full output
    def __iter__(self):
        """Turn into dict with dict(post)"""
        for column in self.__table__.columns:
            yield column.name, getattr(self, column.name)

    # TODO, FIXME
    @staticmethod
    def extract_hashtags(message: str):
        pass

    @staticmethod
    def reference_links(message: str, thread_id: int) -> str:
        """Parse >>id links"""

        pattern = re.compile('\>\>([0-9]+)')
        message_with_links = pattern.sub(
            r'<a href="/threads/%d#\1">&gt;&gt;\1</a>' % thread_id,
            message,
        )
        return message_with_links

    # FIXME: dangerous because untested for vulns
    @staticmethod
    def parse_markdown(timestamp: str, message: str) -> str:
        # FIXME: review, pentest
        bleach = BleachExtension(
            strip=True,
            tags=[
                'h2',
                'h3',
                'h4',
                'h5',
                'h6',
                'blockquote',
                'ul',
                'ol',
                'dl',
                'dt',
                'dd',
                'li',
                'code',
                'sup',
                'pre',
                'br',
                'a',
                'p',
                'em',
                'strong',
            ],
            attributes={
                '*': [],
                'h2': ['id'],
                'h3': ['id'],
                'h4': ['id'],
                'h5': ['id'],
                'h6': ['id'],
                'li': ['id'],
                'sup': ['id'],
                'a': ['href'],  # FIXME: can people be deceptive with this?
            },
            styles={},
            protocols=['http', 'https'],
        )
        slug_timestamp = str(timestamp).replace(' ', '').replace(':', '').replace('.', '')
        FootnoteExtension.get_separator = lambda x: slug_timestamp + '-'
        md = markdown.Markdown(
            extensions=[
                bleach,
                SmartyExtension(
                    smart_dashes=True,
                    smart_quotes=True,
                    smart_ellipses=True,
                    substitutions={},
                ),
                'markdown.extensions.nl2br',
                'markdown.extensions.footnotes',
                'markdown.extensions.toc',
                'markdown.extensions.def_list',
                'markdown.extensions.abbr',
                'markdown.extensions.fenced_code',
            ],
        )
        return md.convert(message)

    # FIXME: what if passed a name which contains no tripcode?
    @staticmethod
    def make_tripcode(name_and_tripcode: str) -> Tuple[str, str]:
        """Create a tripcode from the name field of a post.

        Returns:
            tuple: A two-element tuple containing (in the order of):
                name without tripcode, tripcode.

        Warning:
            Must have `this#format` or it will raise an exception
            related to unpacking.

        """

        name, unhashed_tripcode = name_and_tripcode.split('#', 1)
        tripcode = str(
            base64.b64encode(
                scrypt.hash(unhashed_tripcode, config.SECRET_KEY),
            ),
        )[2:22].replace('/', '-')
        return name, tripcode

    @staticmethod
    def tip_link_stuff(tip_link: str) -> Tuple[Union[str, None], Union[str, None]]:
        if not tip_link:
            return None, None
        elif (not tip_link.startswith('http://')) or (not tip_link.startswith('https://')):
            tip_link = 'http://' + tip_link

        tip_domain = urlparse(tip_link).hostname if tip_link else None
        return tip_link, tip_domain

    @staticmethod
    def word_filter(message):
        word_filters = db.session.query(WordFilter).all()
        for word_filter in word_filters:
            find = re.compile(r'\b' + re.escape(word_filter.find) + r'(ies\b|s\b|\b)', re.IGNORECASE)
            # NOTE: I make it upper because I think it's funnier this way,
            # plus indicative of wordfiltering happening.
            message = find.sub(word_filter.replace.upper(), message)
        return message

    # TODO: rename since now needs request for IP address
    @classmethod
    def from_form(cls, form, request):
        """Create and return a Post.

        The form may be a reply or a new post.

        Returns:
            Post: ...

        """

        # A valid tripcode is a name field containing an octothorpe
        # that isn't the last character.
        if form.name.data and '#' in form.name.data[:-1]:
            name, tripcode = cls.make_tripcode(form.name.data)
        else:
            name = form.name.data
            tripcode = None

        message = form.message.data
        # message link
        try:
            reply_to = int(form.reply_to.data)
            message = cls.reference_links(message, reply_to)
        except (ValueError, AttributeError) as e:
            reply_to = None

        if reply_to and db.session.query(Post).get(reply_to).locked:
            raise Exception('This thread is locked. You cannot reply.')

        # manually generate the timestamp so we can create unique ids
        timestamp = datetime.datetime.utcnow()
        # Parse markdown! FIXME: this probably can be easily exploited...
        message = cls.parse_markdown(timestamp, message)

        # Finally let's do some wordfiltering. Wordfilters are useful because
        # you can catch bad words and flag users that use them.
        message_before_filtering = message
        message = cls.word_filter(message)
        if message_before_filtering != message:
            new_flagged_ip = FlaggedIps(
                ip_address=request.remote_addr,
            )
            db.session.add(new_flagged_ip)
            db.session.commit()

        new_post = cls(
            name=name,
            tripcode=tripcode,
            timestamp=timestamp,
            message=message,
            reply_to=reply_to,
            ip_address=request.remote_addr,
        )
        db.session.add(new_post)
        db.session.commit()

        # increase postcount for tripcode
        if tripcode:
            trip_meta = db.session.query(TripMeta).get(tripcode)
            if trip_meta:
                trip_meta.post_count += 1
            else:
                new_trip_meta = TripMeta(
                    tripcode=tripcode,
                    post_count=1,
                )
                db.session.add(new_trip_meta)
            db.session.commit()

        if reply_to and not form.sage.data:
            original = db.session.query(Post).get(reply_to)
            if not original.permasage:
                original.bumptime = timestamp
                db.session.commit()

        return new_post


class Page(db.Model):
    __tablename__ = 'pages'
    slug = db.Column(db.String(60), primary_key=True)
    title = db.Column(db.String(200))
    body = db.Column(db.String(1000))
    source = db.Column(db.String(700))

    @classmethod
    def from_form(cls, form):
        body = Post.parse_markdown('lol', form.source.data)
        return cls(body=body, slug=form.slug.data, source=form.body.data)


# Create user model.
# TODO: rename admin?
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    login = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(120))
    password = db.Column(db.String(200))

    # Flask-Login integration
    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return self.id
    # Required for administrative interface
    def __unicode__(self):
        return self.username


class Ban(db.Model):
    """Admin can ban by address or network."""
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(100), unique=True)
    reason = db.Column(db.String(100))

    @classmethod
    def from_form(cls, form):
        new_ban = cls(
            address=form.address.data,
            reason=form.reason.data,
        )
        db.session.add(new_ban)
        db.session.commit()

        return new_ban


class BlotterEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(250))
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)


class ConfigPair(db.Model):
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.String(1000), nullable=False)


class WordFilter(db.Model):
    find = db.Column(db.String(100), primary_key=True)
    replace = db.Column(db.String(1000), nullable=False)  # can be html
