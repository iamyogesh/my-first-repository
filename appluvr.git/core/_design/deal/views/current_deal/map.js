function(doc) {if (doc.doc_type=="all_deals")
{
	if (doc.deal_start == undefined || doc.deal_end == undefined ){
		return;
	}
	if (doc.deal_start > doc.deal_end ){
		return;
	}
	var current = parseInt(doc.deal_start);
	while (current < parseInt(doc.deal_end)){
		var key = [current, doc.platform,doc.carrier]
		emit (current, doc);
		emit (key, doc);
		current = current + 1800;
		}
	}
}