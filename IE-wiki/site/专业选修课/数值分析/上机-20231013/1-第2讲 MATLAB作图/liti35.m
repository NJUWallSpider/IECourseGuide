[X,Y]=meshgrid(-3:.125:3);
Z=peaks(X,Y);
meshc(X,Y,Z);
axis([-3 3 -3 3 -10 5])