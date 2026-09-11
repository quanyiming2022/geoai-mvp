"""Grant administrator access to one existing, confirmed local Supabase user."""
import argparse
from migrate import connection


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email',required=True)
    args=parser.parse_args()
    with connection() as conn:
        users=conn.execute('SELECT id,email_confirmed_at FROM auth.users WHERE lower(email)=lower(%s)',(args.email,)).fetchall()
        if len(users)!=1 or not users[0][1]:
            raise SystemExit('Expected exactly one existing confirmed user; sign up and confirm first.')
        conn.execute('INSERT INTO geoai_internal.platform_admins(user_id) VALUES (%s) ON CONFLICT DO NOTHING',(users[0][0],))
    print('Administrator access granted to the existing confirmed account.')


if __name__=='__main__':
    main()
