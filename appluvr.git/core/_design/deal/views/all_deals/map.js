function(doc) {
if (doc.doc_type == "all_deals")
emit(doc._id, doc);
}