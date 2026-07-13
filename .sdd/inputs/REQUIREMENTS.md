-  Review pagination end point on API module because it's don't working.  This dont change data on page changed.
If I call
api/projects?status=all&staffAugmentationOnly=false&page=2&limit=10

get the same data if I call
/api/projects?status=all&staffAugmentationOnly=false&page=2&limit=10

-  Run unit testing related to the pagination, fix or update if it's necesary.
-  Run integration testing related to the pagination, fix or update if it's necesary.