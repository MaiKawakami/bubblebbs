# TODO: move all the model stuff that's templating into here
import re

from . import models


def get_pages():
    return models.db.session.query(models.Page).all()


def get_blotter_entries():
    return models.BlotterEntry.query.order_by(models.BlotterEntry.id.desc()).all()


def complementary_color(my_hex):
    """Returns complementary RGB color

    Example:
    >>>complementaryColor('FFFFFF')
    '000000'
    """
    if my_hex[0] == '#':
        my_hex = my_hex[1:]
    rgb = (my_hex[0:2], my_hex[2:4], my_hex[4:6])
    comp = ['%02X' % (255 - int(a, 16)) for a in rgb]
    return ''.join(comp)


def since_bumptime(bumptime, thread=None, reply=None):
    total_seconds = int((bumptime.now() - bumptime).total_seconds())
    days, seconds = divmod(total_seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    pairs = (
        (days, 'Day'),
        (hours, 'Hour'),
        (minutes, 'Minute'),
        (seconds, 'Second'),
    )
    parts = []
    for value, unit_singular in pairs:
        if value:
            output = '%d %s' % (value, unit_singular)
            if value > 1:
                output += 's'
            parts.append(output)

    very_readable = ', '.join(parts)
    if not very_readable:
        very_readable = 'now'

    datetime_w3c_spec = str(bumptime)[:-3]

    if thread:
        permalink = '<a href="/threads/{permalink}">{parts} ago</a>'.format(
            permalink='%d#%d' % (thread, reply) if reply else thread,
            parts=very_readable,
        )
    elif reply:
        raise Exception('heck no!')
    else:
        permalink = very_readable + ' ago'

    return '''
    <time datetime="{bumptime}" title="{bumptime}">
    {permalink} 
    </time>
    '''.format(bumptime=datetime_w3c_spec, permalink=permalink)
