#! /usr/bin/perl

require '/etc/fido/nodehist.cfg';

use CGI ":standard";

$myname=$ENV{"SCRIPT_NAME"};
#$myname="/cgi-bin/nodehist.cgi" unless $myname;
#$myname="";
@month = qw(Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec);

$query = new CGI;
$address = $query->param("address");

print "Content-Type: text/html\n\n";
print "<html><header><title>Nodelist history search</title></header>\n";
print "<body bgcolor=#fffff0>\n";
print "<center><h2>View history of fidonet node</h2></center>\n";
print "<center><form action=\"$myname\" method=post>\n";
print "Enter 3D fidonet address (like 2:463/68):\n";
print "<input size=11 name=address";
print " value=\"$address\"" if defined($address);
print ">\n";
print "<input type=submit value=\"Get history\">\n";
print "<table border=0><tr>\n";
#print "<td><input type=checkbox name=\"noflags\" checked></td><td> Ignore flags changes</td>\n";
print "<td><input type=checkbox name=\"noflags\"" . checked("noflags") . "></td><td> Ignore flags changes</td>\n";
print "<td><input type=checkbox name=\"nophone\"" . checked("nophone") . "></td><td> Ignore phone changes</td></tr>\n";
print "</tr><tr>";
print "<td><input type=checkbox name=\"nospeed\"" . checked("nospeed") . "></td><td> Ignore speed changes</td>\n";
print "<td><input type=checkbox name=\"nostatus\"" . checked("nostatus") . "></td><td> Ignore hold/down/pvt/hub status changes</td>\n";
print "</tr><tr>";
print "<td><input type=checkbox name=\"nolocation\"" . checked("nolocation") . "></td><td> Ignore location changes</td>\n";
print "<td><input type=checkbox name=\"noname\"" . checked("noname") . "></td><td> Ignore node name changes</td>\n";
print "</tr></table>\n";
print "</form></center>\n";

if (!defined($address)) {
	print end_html();
	exit(0);
}

unless ($address =~ /^(\d+):(\d+)\/(\d+)$/) {
	print "Incorrect address '$address'!";
	print end_html();
	exit(0);
}
($zone, $net, $node) = ($1, $2, $3);

use DBI;

unless ($dbh = DBI->connect($dsn, $myuser, $mypwd, { PrintError => 0 })) {
	print "Cannot connect to SQL server, try later\n";
	print end_html();
	exit(0);
}

# Check only last region for this network
if ($net != $zone) {
	$sth=$dbh->prepare("select region from nets where zone=$zone and net=$net order by date desc limit 1");
	unless ($sth->execute()) {
		$err = "$DBI::err ($DBI::errstr)";
		$dbh->disconnect();
		print STDERR "mysql error: $err\n";
		print "SQL-server error, try later\n";
		print end_html();
		exit(0);
	}
	($region) = $sth->fetchrow_array();
	$sth->finish();
	$region = 0 if !defined($region);
} else {
	$region = $zone;
}

#print "\n<!-- select date, daynum, line from $mytable where zone=$zone and net=$net and node=$node order by date -->\n";
$sth=$dbh->prepare("select net, node, date, daynum, line from $mytable where zone=$zone and (net=$net and (node=$node or node=0) or net=$region and node=0 or net=$zone and node=0) order by date, zone, net, node");
unless ($sth->execute()) {
	$err = "$DBI::err ($DBI::errstr)";
	$dbh->disconnect();
	print STDERR "mysql error: $err\n";
	print "SQL-server error, try later\n";
	print end_html();
	exit(0);
}
print "<center><h2>History of node $address:</h2></center>\n";
print "<!-- noflags='" . $query->param("noflags") . "'-->\n" if defined($query->param("noflags"));
print "<pre>\n";
$name = $phone = $flags = $location = $status = $speed = $sysname = '';
$found = 0;
$prevdate = '';
while (($fnet, $fnode, $date, $daynum, $line) = $sth->fetchrow_array()) {
	$nozone = $noregion = $nonet = 0 if $date ne $prevdate;
	$prevdate = $date;
	if ($fnet != $net || $fnode != $node) {
		# zone, net or region entry
		next if $line;
		if ($fnet == $zone) {
			$nozone = 1;
		} elsif ($fnet == $region) {
			$noregion = 1;
		} else {
			$nonet = 1;
		}
		next;
	}
	$found = 1;
	if ($date =~ /^(\d+)-(\d+)-(\d+)$/) {
		$date = sprintf('%2u&nbsp;%s&nbsp;%u', $3, $month[$2-1], $1);
	}
	$h = sprintf("<b> %12s, nodelist.%03d: </b>", $date, $daynum);
	if ($line) {
		if ($line =~ /^([^,]*),\d+,([^,]*),([^,]*),([^,]*),([^,]*),([^,]*)(?:,(.*))?$/) {
			@line = ($1, $2, $3, $4, $5, $6, $7);
			if (($status   ne $line[0] && !defined($query->param("nostatus"))) ||
			    ($name     ne $line[1] && !defined($query->param("noname"))) ||
			    ($location ne $line[2] && !defined($query->param("nolocation"))) ||
			    ($sysname  ne $line[3] && !defined($query->param("nosysname"))) ||
			    ($phone    ne $line[4] && !defined($query->param("nophone"))) ||
			    ($speed    ne $line[5] && !defined($query->param("nospeed"))) ||
			    ($flags    ne $line[6] && !defined($query->param("noflags")))) {
				print "$h$line\n";
			} else {
				#print "$h<code>$line</code> (not changed)</td></tr>\n";
				#print "<!-- oldflags: '$flags', flags: '$line[6]' -->\n";
			}
			($status, $name, $location, $sysname, $phone, $speed, $flags) = @line;
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
		} else {
			$addinfo = "";
		}
		print "${h}Node removed from the nodelist$addinfo\n";
		$name = $phone = $flags = $location = $status = $speed = $sysname = '';
	}
}
print "</pre>\n";
$sth->finish();
$dbh->disconnect();
print "Node not found\n" unless $found;
print end_html();
exit(0);

sub checked
{
	my ($param) = @_;
	return defined($query->param($param)) ? " checked" : "";
}
