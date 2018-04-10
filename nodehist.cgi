#! /usr/bin/perl

use warnings;
use strict;

our ($dsn, $myuser, $mypwd, $mytable, $myname, $maxresults, $min_word_len);

require '/etc/fido/nodehist.cfg';

use CGI ":standard";
use DBI;

my $debug = 0;
$myname //= $ENV{"SCRIPT_NAME"};
#$myname //= "/cgi-bin/nodehist.cgi";
#$myname="";
$maxresults //= 200;
$min_word_len //= 3; # Less then default 4, required ft_min_word_len=3 in my.cnf
my @month = qw(Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec);

my $q = new CGI;
my $address = $q->param("address");
my $name = $q->param("name");

my $badnl = (defined($q->param("badnl")) ? 1 : 0);

print "Content-Type: text/html\n\n";
print "<html><header><title>Nodelist history search</title></header>\n";
print "<body bgcolor=#fffff0>\n";

my $dbh = DBI->connect($dsn, $myuser, $mypwd, { PrintError => 0, mysql_enable_utf8 => 1 })
    or endpage("Cannot connect to SQL server, try later");

my $sth = $dbh->prepare("select distinct date from $mytable order by date");
unless ($sth->execute()) {
    print STDERR "mysql error: $DBI::err ($DBI::errstr)\n";
    endpage("SQL-server error, try later");
}
my $nodelists = 0;
my ($firstdate, $lastdate);
while (my ($date) = $sth->fetchrow_array()) {
    $date =~ s/-/./g;
    $firstdate = $date unless $firstdate;
    $lastdate = $date;
    $nodelists++;
}
$sth->finish();

print "<p><center><h2>View history of fidonet node</h2>\n";
print "Using $nodelists nodelists, first: $firstdate, last: $lastdate</center>\n";
print "<p><center><form action=\"$myname\" method=get>\n";
print "Enter 3D fidonet address (like 2:463/68):\n";
print "<input size=11 name=address";
print " value=\"" . quote($address) . "\"" if defined($address);
print ">\n";
print "<input type=submit value=\"Get history\">\n";
print "<table border=0><tr>\n";
#print "<td><input type=checkbox name=\"noflags\" checked></td><td> Ignore flags changes</td>\n";
print "<td><input type=checkbox name=\"noflags\"" . checked("noflags") . "></td><td> Ignore flags changes</td>\n";
print "<td><input type=checkbox name=\"nophone\"" . checked("nophone") . "></td><td> Ignore phone changes</td>\n";
print "</tr><tr>";
print "<td><input type=checkbox name=\"nospeed\"" . checked("nospeed") . "></td><td> Ignore speed changes</td>\n";
print "<td><input type=checkbox name=\"nostatus\"" . checked("nostatus") . "></td><td> Ignore hold/down/pvt/hub status changes</td>\n";
print "</tr><tr>";
print "<td><input type=checkbox name=\"nolocation\"" . checked("nolocation") . "></td><td> Ignore location changes</td>\n";
print "<td><input type=checkbox name=\"noname\"" . checked("noname") . "></td><td> Ignore node name changes</td>\n";
print "</tr><tr>";
print "<td><input type=checkbox name=\"nosysname\"" . checked("nosysname") . "></td><td> Ignore sysop changes</td>\n";
print "<td><input type=checkbox name=\"badnl\"" . checked("badnl") . "></td><td> Show bad nodelists</td>\n";
print "</tr></table></form>\n";
print "<b>Do not know node number? Search by sysop name</b><br />\n";
print "<form action=\"$myname\" method=get>\n";
print "Enter sysop name: <input size=30 name=name";
print " value=\"" . quote($name) . "\"" if defined($name);
print "><input type=submit value=\"Search for sysop\">\n";
print "</form></center>\n";

endpage() if !defined($address) && !defined($name);

if (defined($name)) {
    #$_ = $name;
    #s/[\?\*]//g;
    #if (length($_)<4) {
    #    endpage("Search string too short (min 4 chars)");
    #}
    #$name =~ s/ /_/g;
    #$name =~ s/[^-a-zA-Z0-9\?\*,]/\\$&/g;
    #$name =~ s/\?/_/g;
    #$name =~ s/\*/%/g;
    #$name = '%name%';
    #$query="select distinct zone, node, net from $mytable where line like '$name' order by zone, net, node limit ".($maxresults+1);
    #$query="select distinct zone, net, node from $mytable where $match order by $match desc, date asc limit ".($maxresults+1);
    #$match="match (line) against(" . $dbh->quote($name) . ")";
    my @words = split(/\s+/, $name);
    foreach (@words) {
        if (length($_) < $min_word_len) {
            endpage("Too short word for search: $_");
        }
        $_ = "match (line) against(" . $dbh->quote($_) . ")";
    }
    my $match = join(' AND ', @words);
    my $query = "select zone, net, node from $mytable where $match group by zone, net, node order by min(date) limit " . ($maxresults+1);
    debug($query);
    $sth = $dbh->prepare($query);
    unless ($sth->execute()) {
        print STDERR "mysql error: $DBI::err ($DBI::errstr)\n";
        endpage("SQL-server error, try later");
    }
    my @nodes;
    while (my @arr = $sth->fetchrow_array()) {
        push(@nodes, "$arr[0]:$arr[1]/$arr[2]");
        debug("Result: $arr[0]:$arr[1]/$arr[2]");
    }
    $sth->finish();
    endpage("No nodes found") if !@nodes;
    print "<p><table border=0>\n";
    for (my $i = 0; $i <= $#nodes; $i++) {
        last if $i == $maxresults;
        next if $nodes[$i] !~ /^(\d+):(\d+)\/(\d+)$/;
        my ($zone, $net, $node) = ($1, $2, $3);
        debug("found: $zone:$net/$node");
        #$sth->prepare("select date, if (line like '$name', line, '') from $mytable where zone=$zone and net=$net and node=$node order by date");
        $query="select date, if ($match, line, '') from $mytable where zone=$zone and net=$net and node=$node order by date";
        debug($query);
        $sth = $dbh->prepare($query);
        unless ($sth->execute()) {
            print STDERR "mysql error: $DBI::err ($DBI::errstr)\n";
            endpage("SQL-server error, try later");
        }
        my ($firstdate, $lastdate, $location, $sysop);
        $firstdate = $lastdate = $location = $sysop = '';
        while (my ($date, $line) = $sth->fetchrow_array()) {
            if (!$line) {
                $lastdate=$date if !$lastdate;
                next;
            }
            $lastdate = '';
            next if $firstdate;
            $firstdate = $date;
            next if $line !~ /^[^,]*,\d+,[^,]*,([^,]*),([^,]*),[^,]*,[^,]*(?:,.*)?$/;
            ($location, $sysop) = ($1, $2);
        }
        $sth->finish();
        endpage("Internal error") unless $firstdate;
        if ($lastdate) {
            # get previous date for $lastdate
            # we need date of last occurence, not date of removing
            $sth=$dbh->prepare("select distinct date from $mytable where date<'$lastdate' order by date desc limit 1");
            unless ($sth->execute()) {
                print STDERR "mysql error: $DBI::err ($DBI::errstr)\n";
                endpage("SQL-server error, try later");
            }
            my $date;
            $lastdate = $date if ($date) = $sth->fetchrow_array();
            $sth->finish();
        }
        $firstdate =~ s/-/./g;
        $lastdate = "now" if !$lastdate;
        $lastdate =~ s/-/./g;
        print "<tr><td> <a href=$myname?address=$zone%3A$net%2F$node>$zone:$net/$node</a> </td>";
        print "<td> $sysop </td>";
        print "<td> <small>from</small> $location </td>\n";
        print "<td> $firstdate - $lastdate </td></tr>\n";
    }
    print "</table></p>\n";
    print "<p><b>  More results skipped</b></p>\n" if $#nodes >= $maxresults;
    endpage();
}

unless ($address =~ /^(\d+):(\d+)\/(\d+)$/) {
    endpage("Incorrect address '$address'!");
}
my ($zone, $net, $node) = ($1, $2, $3);
my $region;

# Check only last region for this network
if ($net != $zone) {
    $sth = $dbh->prepare("select region from nets where zone=$zone and net=$net order by date desc limit 1");
    unless ($sth->execute()) {
        print STDERR "mysql error: $DBI::err ($DBI::errstr)\n";
        endpage("SQL-server error, try later");
    }
    ($region) = $sth->fetchrow_array();
    $sth->finish();
    $region = 0 if !defined($region);
} else {
    $region = $zone;
}

#print "\n<!-- select date, daynum, line from $mytable where zone=$zone and net=$net and node=$node order by date -->\n";
my $query = "select net, node, date, daynum, line from $mytable where zone=$zone and (net=$net and (node=$node or node=0) or net=$region and node=0 or net=$zone and node=0) order by date, zone, net, node";
debug($query);
$sth = $dbh->prepare($query);
unless ($sth->execute()) {
    print STDERR "mysql error: $DBI::err ($DBI::errstr)\n";
    endpage("SQL-server error, try later");
}
print "<center><h2>History of node $address</h2></center>\n";
print "<pre>\n";
my ($phone, $flags, $location, $status, $speed, $sysname);
$name = $phone = $flags = $location = $status = $speed = $sysname = '';
my ($addinfo, $hremoved, $wasnet, $found);
$addinfo = $hremoved = '';
$found = $wasnet = 0;
my ($nozone, $noregion, $nonet);
my $prevdate = '';
while (my ($fnet, $fnode, $date, $daynum, $line) = $sth->fetchrow_array()) {
    if ($date ne $prevdate) {
        debug("date: $date, prevdate: $prevdate, addinfo: '" . ($addinfo // '') . "', hremoved: '$hremoved', wasnet: $wasnet");
        if (defined($addinfo) && $hremoved) {
            if ($wasnet) {
                # node completely removed
                print "<em>Node removed from the nodelist</em>\n";
                $addinfo = undef;
                $hremoved = '';
            } elsif ($badnl) {
                print "${hremoved}<em>Node removed from the nodelist$addinfo</em>\n";
                $addinfo = undef;
                $hremoved = '';
            }
        }
        $nozone = $noregion = $nonet = $wasnet = 0;
        $prevdate = $date;
    }
    if ($date =~ /^(\d+)-(\d+)-(\d+)$/) {
        $date = sprintf('%2u&nbsp;%s&nbsp;%u', $3, $month[$2-1], $1);
    }
    my $h = sprintf("<b> %12s, nodelist.%03d: </b>", $date, $daynum);
    if ($fnet != $net || $fnode != $node) {
        # zone, net or region entry
        if ($line) {
            $wasnet = 1 if $fnet == $net;
        } else {
            if ($fnet == $zone) {
                $nozone = 1;
            } elsif ($fnet == $region) {
                $noregion = 1;
            } else {
                $nonet = 1;
            }
        }
        next;
    }
    $found = 1;
    if ($line) {
        $line =~ s/ /_/g;
        if ($line =~ /^([^,]*),\d+,([^,]*),([^,]*),([^,]*),([^,]*),([^,]*)(?:,(.*))?$/) {
            my @line = ($1, $2, $3, $4, $5, $6, $7);
            if (($status   ne $line[0] && !defined($q->param("nostatus"))) ||
                ($name     ne $line[1] && !defined($q->param("noname"))) ||
                ($location ne $line[2] && !defined($q->param("nolocation"))) ||
                ($sysname  ne $line[3] && !defined($q->param("nosysname"))) ||
                ($phone    ne $line[4] && !defined($q->param("nophone"))) ||
                ($speed    ne $line[5] && !defined($q->param("nospeed"))) ||
                ($flags    ne $line[6] && !defined($q->param("noflags")))) {
                print "$h$line\n";
            } else {
                #print "$h<code>$line</code> (not changed)</td></tr>\n";
                #print "<!-- oldflags: '$flags', flags: '$line[6]' -->\n";
            }
            ($status, $name, $location, $sysname, $phone, $speed, $flags) = @line;
            $hremoved = '';
        } else {
            #print "<!-- Cannot parse line '$line' -->\n";
        }
    } else {
        if ($nozone && ($noregion || $net == $zone)) {
            # noregion check needed because Ward lost "Zone,2" line in nodelist.075 2007
            $addinfo = " (with all zone $zone)";
        } elsif ($noregion) {
            $addinfo = " (with all region $region)";
        } elsif ($nonet) {
            $addinfo = " (with all network $net)";
        } elsif ($fnode == 0) {
            $addinfo = '';    # single nodelist without node is bad
        } else {
            $addinfo = undef;
        }
        if (!defined($addinfo) || $badnl) {
            print "${h}<em>Node removed from the nodelist" . ($addinfo // '') . "</em>\n";
            $name = $phone = $flags = $location = $status = $speed = $sysname = '';
        } else {
            $hremoved = $h;
        }
    }
}
if ($hremoved) {
    # Assume the last existing nodelist is not bad
    print "${hremoved}<em>Node removed from the nodelist$addinfo</em>\n";
}
print "</pre>\n";
$sth->finish();
print "Node not found\n" unless $found;
endpage();

sub checked
{
    my ($param) = @_;
    return defined($q->param($param)) ? " checked" : "";
}

sub endpage
{
    my ($message) = @_;
    $dbh->disconnect() if defined($dbh);
    print "$message\n" if defined($message);
    print "<p align=center><small><em>NodeHist created by <a href=mailto:site\@gul.kiev.ua>Pavel Gulchouck</a> <a href=mailto:Pavel_Gulchouck\@f68.n463.z2.fidonet.org>2:463/68</a></em></small></p>\n";
    print "</body></html>\n";
    exit(0);
}

sub debug
{
    my ($str) = @_;
    return unless $debug;
    print "\n<!-- $str -->\n";
}

sub quote
{
    my ($str) = @_;
    #$str =~ s/[^-a-zA-Z0-9., _]/sprintf('&#%02x;', ord($&))/ge;
    $str =~ s/"/&quot;/g;
    return $str;
}
