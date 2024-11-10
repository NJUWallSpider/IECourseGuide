x=-3:0.1:3;   y=1:0.1:5;
     [X,Y]=meshgrid(x,y);
     Z=(X+Y).^2;
     mesh(X,Y,Z)     