
def userid: $ENV.USER_ID;
def timelimit: $ENV.TIMELIMIT | tonumber; # maximum difference between snowflakes less than 7 hours apart
def grouptimelimit: $ENV.GROUPTIMELIMIT | tonumber; # maximum difference between messages that are grouped together

def typeok: .type == 0 or .type == 6 or .type == 19;

def ignore(f): . as $x | f | $x;

def groupinitial:
  . as $a
  | if .[0].author.id != userid then error("message not by user found: \(.[0] | tojson)") | {emit: false} else . end
  | (.[0].id | tonumber) as $id
  | try reduce .[] as $msg ({msgs: [], idx: 0, seen: {}};
							.idx += 1
							 | if $msg | $id - (.id|tonumber) > grouptimelimit
											 or userid != .author.id
											 or (typeok | not)
							   then error else . end
							 | .msgs += [$msg]
							 | .seen[$msg.id] = true)
	catch .
  | if (.msgs | length) == 0 then error("\($a | tojson): no valid oober messages") else . end
  | {item: {msgs: .msgs, ctx: $a[.idx:]}} + .seen;

def uniqueids(stream):
  foreach stream as $s ({};
						$s[0].id as $y
						 | if .[$y] then .emit = false
						   else .emit = true
							 | . as $state
							 | try (. += ($s | groupinitial))
							   catch (error | $state | .emit = false)
						   end;
						if .emit then .item else empty end);



def user: "\(.username)#\(.discriminator) (ID: \(.id))";

def defcontent: ": \(.content)";

def msgcontent:
  {
	"6": " pinned message \(.message_reference.id)",
	"7": " joined",
	"18": " created a thread with name \(.content).",
    "19": " replied to \(.message_reference.message_id) with \(.content)"
  }[.type | tostring] // ": \(.content)";

def attachments:
  .attachments
  | map("\nAttached file: \(.filename)")
  | add // "";

def reactions:
  if (.reactions | length) > 0 then
	["\nReactions: ", (.reactions[] | "\(.emoji.name): \(.count)")]
	| add
  else "" end;

def embeds:
  if (.embeds | length) > 0 then
	["\nEmbeds: ", (.embeds[] | "\n\(tojson)")]
	| add
  else "" end;
								  
def text:
  "\(.id) \(.timestamp[:-13]): \(.author | user)\(msgcontent)\(attachments)\(reactions)\(embeds)";
						

uniqueids(fromstream(1 | truncate_stream(inputs)) | select(.[0] | typeok))
  | (.msgs[0].id | tonumber) as $id
  | .ctx |= map(select($id - (.id|tonumber) < timelimit))
  | { prompt: .ctx
	  | reverse
	  | map(text)
	  | join("\n")
	  | "Continue the conversation as oober.\n\n\(.)\n---\n"
    , completion: .msgs
	  | reverse
	  | map(.reactions = [] | text)
	  | join("\n")}
		   
