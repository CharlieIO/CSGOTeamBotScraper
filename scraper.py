import time
import os
import urllib2
import re
import psycopg2
import urlparse
import datetime
from bs4 import BeautifulSoup

urlparse.uses_netloc.append("postgres")
url = urlparse.urlparse(os.environ["MORPH_DATABASE_URL"])


def auto_scrape():
    '''
    Used to update the database automagically
    '''
    tcount = 0  # team count
    pcount = 0  # player count
    teamlink = teamLinks()  # gets dict with teams as keys and links as values
    for tname in teamlink:  # go through each team on top 400 list
        tlink = teamlink[tname]  # sets a variable for the team's HLTV link
        # obtains a list of players, and a dictionary containing player names
        # and links
        players, playerlink = tScrape(tlink)
        # (anyone who has been on a top 400 team)
        win, draw, loss, mapsplayed, kills, deaths, rounds, kdratio = statScrape(
            tlink)
        for player in playerlink:  # look at each player in the playerlink list
            try:
                plink = playerlink[player]  # set a variable for their link
                # set variables for their teammates
                p1, p2, p3, p4 = otherPlayers(plink)
                pname, age, team, k, hsp, d, rating, u1, u2, u3, u4 = pStats(
                    plink)  # get player stats and teammates (u is unused variables)
                if tname == team:  # if the players are on the correct team, update DB
                    team_database_update(
                        tname, p1, p2, p3, p4, player, win, draw, loss, rounds, tlink)
                    tcount += 1  # increment teams added
                    print tname + ' has been modified. \n' + str(tcount) + ' teams modified.',
                else:
                    # if the team is missing a link, update DB
                    team_database_update_nolink(team, p1, p2, p3, p4, player)
                    tcount += 1  # increment teams added
                    print team + ' has been modified. \n' + str(tcount) + ' teams modified.',
                player_database_update(
                    player,
                    pname,
                    age,
                    team,
                    k,
                    d,
                    hsp,
                    rating,
                    plink)  # regardless, update the player DB
                pcount += 1  # increment players added
                print player + ' has been modified. \n' + str(pcount) + ' players modified. #' + team,
                time.sleep(3)  # reduce load on HLTV servers
            except:
                print 'error'
                pass
                # name, age, team, K, HSP, D, Rating
        time.sleep(3)
    print 'UPDATE COMPLETE :)'


def teamLinks():
    '''
    extracts names of teams, and their links
    @return: dictionary with name as key and link as value
    '''
    namelink = {}
    req = urllib2.Request(
        'http://www.hltv.org/?pageid=182&mapCountOverride=10',
        headers={
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.111 Safari/537.36"})
    con = urllib2.urlopen(req)
    source = con.read()  # get source code
    soup = BeautifulSoup(source, 'html.parser')
    for link in soup.find_all('a', href=True):  # finds all links in the HTML
        if re.findall(
                'pageid=179',
                link['href']):  # pageid=179 is a player's page
            namelink[link.get_text().encode('latin1').strip()] = link.get(
                'href').encode('latin1').replace('/', '')
            # strips spaces from links, and removes the beginning /
            # (preference, could function with the /)
    return namelink  # returns dictionary with name as key and link as value


def otherPlayers(plink):
    '''
    @param plink: player's link
    @return: all the team values we care about
    '''
    u1, u2, u3, u4, u5, u6, u7, p1, p2, p3, p4 = pStats(
        plink)  # again, u is variables we recieve but don't need
    return p1, p2, p3, p4


def pStats(plink):
    '''
    Extracts player's stats given a link to their page
    @param plink: a link to the player's page
    @return: depending on how much information is found, can return variable amount
    '''
    req = urllib2.Request(
        'http://www.hltv.org/' +
        str(plink),
        headers={
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.111 Safari/537.36"})
    con = urllib2.urlopen(req)
    source = con.read()
    soup = BeautifulSoup(source, 'html.parser')
    stats = []
    names = []
    personalstats = []  # stats such as name and age
    for stat in soup.find_all(
            style="font-weight:normal;width:100px;float:left;text-align:right;color:black"):
        if '%' in stat.get_text():  # HS percentage has a percent sign that must be removed
            stats += [stat.get_text().replace('%', '')]
        else:
            stats += [stat.get_text()]
    for stat in soup.find_all(
            style="font-weight:normal;width:185px;float:left;text-align:right;color:black;"):
        if '-' == stat.get_text():
            # fix for no age listed
            personalstats += [stat.get_text().replace('-', '99')]
        else:
            personalstats += [stat.get_text()]
    for stat in soup.find_all(
            style="font-weight:normal;width:100px;float:left;text-align:right;color:black;font-weight:bold"):
        stats += [stat.get_text()]
    for name in soup.find_all('b'):
        if name.get_text()[0] == "'":  # obtains the names of teammates
            names += [name.get_text().strip("'")]
    if len(names) == 4 and len(personalstats) == 4 and len(
            stats) == 10:  # full set of stats
        print '\n', names,
        return personalstats[0], personalstats[1], personalstats[3], stats[0], stats[1], stats[2], stats[9], names[
            0], names[1], names[2], names[3]  # in order: name, age, team, kills, HSP, deaths, rating, 4 teammates
    elif len(personalstats) == 4 and len(stats) == 10:  # team doesn't have 5 members
        print '\nIncomplete team or overloaded (>5 members)',
        return personalstats[0], personalstats[1], personalstats[3], stats[
            0], stats[1], stats[2], stats[9], '', '', '', ''  # all but the teammates
    else:
        # if missing anything else, just return empty strings.
        return '', '', '', '', '', '', '', '', '', '', ''


def tScrape(teamlink):
    '''
    Gets all players that have been on a team + their links
    @param teamlink: takes dictionary with teams  and links
    @return: returns a list of players as well as a dictionary with players names and links
    '''
    players = []
    req = urllib2.Request(
        'http://www.hltv.org/' +
        teamlink,
        headers={
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.111 Safari/537.36"})
    con = urllib2.urlopen(req)
    source = con.read()
    soup = BeautifulSoup(source, 'html.parser')
    playerlink = {}
    for link in soup.find_all('a', href=True):
        if re.findall(
                'pageid=173',
                link['href']):  # pageid=173 is the id for a player's page
            if '(' in link.get_text(
            ):  # if it is a relevant plink it will have '('
                playerlink[link.get_text().split(' (')[0]] = link.get(
                    'href').replace('/', '')  # removes / from link
                players += [link.get_text().split(' (')[0]]
    return players, playerlink  # every player that has been on a team.


def player_database_update(player, name, age, team, k, d, hsp, rating, link):
    '''
    using psycopg2 updates the player DB
    @param player: player's in-game-name
    @param name: player's IRL names
    @param age: age of the player
    @param team: player's listed primary team
    @param k: kills
    @param d: deaths
    @param hsp: headshot percentage
    @param rating: HLTV rating for that player
    @param link: link to their HLTV page
    @return: none
    '''
    conn = psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )
    cur = conn.cursor()
    cur.execute("SELECT LINK FROM CSGO_PLAYERS")
    linklist = cur.fetchall()
    try:
        if (link,) not in linklist:  # if not already in the DB, add them
            cur.execute(
                "INSERT INTO CSGO_PLAYERS (PLAYER, IRLNAME, AGE, TEAM, KILLS, DEATHS, HSP, RATING, LINK) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (player,
                 name,
                 age,
                 team,
                 k,
                 d,
                 hsp,
                 rating,
                 link))
            print '\nNew Player Added Successfully',
        else:  # if already in the DB, just update each field
            cur.execute(
                "UPDATE CSGO_PLAYERS SET IRLNAME=(%s) WHERE LINK=(%s)", (name, link))
            cur.execute(
                "UPDATE CSGO_PLAYERS SET AGE=(%s) WHERE LINK=(%s)", (age, link))
            cur.execute(
                "UPDATE CSGO_PLAYERS SET TEAM=(%s) WHERE LINK=(%s)", (team, link))
            cur.execute(
                "UPDATE CSGO_PLAYERS SET KILLS=(%s) WHERE LINK=(%s)", (k, link))
            cur.execute(
                "UPDATE CSGO_PLAYERS SET DEATHS=(%s) WHERE LINK=(%s)", (d, link))
            cur.execute(
                "UPDATE CSGO_PLAYERS SET HSP=(%s) WHERE LINK=(%s)", (hsp, link))
            cur.execute(
                "UPDATE CSGO_PLAYERS SET RATING=(%s) WHERE LINK=(%s)", (rating, link))
            # cur.execute("UPDATE CSGO_PLAYERS SET LINK=(%s) WHERE LINK=(%s)", (link, link))
            print '\nExisting Player Updated',
        conn.commit()
        conn.close()
    except:
        conn.close()
        pass


def team_database_update(
        tname,
        p1,
        p2,
        p3,
        p4,
        p5,
        win,
        draw,
        loss,
        rounds,
        link):
    '''
    Same as player DB update but for the team info
    @param tname: name of the team
    @param p1: roster of the team
    @param p2: "
    @param p3: "
    @param p4: "
    @param p5: "
    @param win: wins the team has
    @param draw: draws " " "
    @param loss: losses " " "
    @param rounds: rounds the team has played
    @param link: link to the team page
    @return: none
    '''
    conn = psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )
    cur = conn.cursor()
    cur.execute("SELECT LINK FROM csgo_teams")
    linklist = cur.fetchall()
    if (link,) not in linklist:
        cur.execute(
            "INSERT INTO CSGO_TEAMS (TEAM_NAME, PLAYER1, PLAYER2, PLAYER3, PLAYER4, PLAYER5, WINS, DRAWS, LOSSES, ROUNDS, LINK) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (tname,
             p1,
             p2,
             p3,
             p4,
             p5,
             win,
             draw,
             loss,
             rounds,
             link))  # if not already in the DB, add them
        print '\nNew Team Added Successfully',
    else:  # if else, update their info
        cur.execute(
            "UPDATE CSGO_TEAMS SET TEAM_NAME=(%s) WHERE LINK= (%s)", (tname, link))
        cur.execute(
            "UPDATE CSGO_TEAMS SET PLAYER1=(%s) WHERE LINK= (%s)", (p1, link))
        cur.execute(
            "UPDATE CSGO_TEAMS SET PLAYER2=(%s) WHERE LINK= (%s)", (p2, link))
        cur.execute(
            "UPDATE CSGO_TEAMS SET PLAYER3=(%s) WHERE LINK= (%s)", (p3, link))
        cur.execute(
            "UPDATE CSGO_TEAMS SET PLAYER4=(%s) WHERE LINK= (%s)", (p4, link))
        cur.execute(
            "UPDATE CSGO_TEAMS SET PLAYER5=(%s) WHERE LINK= (%s)", (p5, link))
        cur.execute(
            "UPDATE CSGO_TEAMS SET WINS=(%s) WHERE LINK= (%s)", (win, link))
        cur.execute(
            "UPDATE CSGO_TEAMS SET DRAWS=(%s) WHERE LINK= (%s)", (draw, link))
        cur.execute(
            "UPDATE CSGO_TEAMS SET LOSSES=(%s) WHERE LINK= (%s)", (loss, link))
        cur.execute(
            "UPDATE CSGO_TEAMS SET ROUNDS=(%s) WHERE LINK= (%s)", (rounds, link))
        print '\nExisting Team Updated',
    conn.commit()
    conn.close()


def team_database_update_nolink(tname, p1, p2, p3, p4, p5):
    '''
    If the team is missing the team link (not in top 400) update this way
    @param tname: team name
    @param p1: roster
    @param p2: "
    @param p3: "
    @param p4: "
    @param p5: "
    @return: none
    '''
    conn = psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )
    cur = conn.cursor()
    cur.execute("SELECT TEAM_NAME FROM csgo_teams")
    teamnames = cur.fetchall()
    if (tname.encode('ascii', 'replace'),) not in teamnames:
        cur.execute(
            "INSERT INTO CSGO_TEAMS (TEAM_NAME, PLAYER1, PLAYER2, PLAYER3, PLAYER4, PLAYER5) VALUES (%s, %s, %s, %s, %s, %s)",
            (tname.encode(
                'ascii',
                'replace'),
                p1,
                p2,
                p3,
                p4,
                p5))
        print '\nNew Team (Incomplete) Added Successfully',
    else:
        cur.execute(
            "UPDATE CSGO_TEAMS SET PLAYER1=(%s) WHERE TEAM_NAME= (%s)", (p1, tname))
        cur.execute(
            "UPDATE CSGO_TEAMS SET PLAYER2=(%s) WHERE TEAM_NAME= (%s)", (p2, tname))
        cur.execute("UPDATE CSGO_TEAMS SET PLAYER3=(%s) WHERE TEAM_NAME= (%s)",
                    (p3, tname))  # functions identically to other update funcs
        cur.execute(
            "UPDATE CSGO_TEAMS SET PLAYER4=(%s) WHERE TEAM_NAME= (%s)", (p4, tname))
        cur.execute(
            "UPDATE CSGO_TEAMS SET PLAYER5=(%s) WHERE TEAM_NAME= (%s)", (p5, tname))
        print '\nExisting Team Updated',
    conn.commit()
    conn.close()


def statScrape(teamlink):
    '''
    obtains the team stats
    @param teamlink: link to the team page
    @return: win, draw, loss, maps played, kills, deaths, rounds played, K/D ratio
    '''
    req = urllib2.Request(
        'http://www.hltv.org/' +
        teamlink,
        headers={
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.111 Safari/537.36"})
    con = urllib2.urlopen(req)
    source = con.read()
    soup = BeautifulSoup(source, 'html.parser')
    otherstats = []
    for stat in soup.find_all(
            style="font-weight:normal;width:140px;float:left;color:black;text-align:right;"):
        windrawloss = stat.get_text().split(' / ')
    for stat in soup.find_all(
            style="font-weight:normal;width:180px;float:left;color:black;text-align:right;"):
        otherstats += [stat.get_text()]
    return windrawloss[0], windrawloss[1], windrawloss[2], otherstats[0], otherstats[
        1], otherstats[2], otherstats[3], otherstats[4]  # win, draw, loss
    # other stats are maps played, total kills, total deaths, rounds played,
    # K/D ratio


def info():
    conn = psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )
    cur = conn.cursor()
    cur.execute("SELECT * FROM csgo_teams WHERE TEAM_NAME='fnatic'")
    teamnames = cur.fetchall()
    print teamnames

if datetime.datetime.today().weekday() == 0:
    auto_scrape()
