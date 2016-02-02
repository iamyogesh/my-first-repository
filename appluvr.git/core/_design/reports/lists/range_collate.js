function (head, req) {

  //Placeholder for result.
  var row, tot=0;
  var ctr = [0,0,0,0,0,0,0,0,0,0,0];
  var rng = ["0-5","6-10","11-15","16-20","21-25","26-30","31-35","36-40","41-45","46-50",">50"];
  var final_result = { data:null, total:null};
  
  //Process each row/doc, do range-based and total counting.
  while ( row = getRow()) {   
    var bucket = 0;
    if(row.value["number_of_apps"]>0){
      bucket = Math.floor((row.value["number_of_apps"]-1)/5);
    } 
    if(bucket>10)
      bucket=10;    
    //count in range
    ctr[bucket] = ctr[bucket]+1;
    //total count
    tot++;               
  }

  //Populate range vs count into data JSON.
  var data = [];
  for(var i=0; i<rng.length ; i++){
    //Pile on result rows.
    //data[rng[i]] = ctr[i];
    data[i] = {"name":rng[i],"count":ctr[i]};
  }

  //Final Output
  final_result.data = data;
  final_result.total = tot;
  send(toJSON(final_result));
}