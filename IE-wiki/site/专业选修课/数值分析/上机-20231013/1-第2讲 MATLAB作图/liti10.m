x=-3:0.1:3;   y=1:0.1:5;
     [X,Y]=meshgrid(x,y);
     Z=(X+Y).^2;
     subplot(2,2,1); mesh(X,Y,Z)
     subplot(2,2,2);mesh(X,Y,Z);view(50,-34)
     subplot(2,2,3);mesh(X,Y,Z);view(-60,70) 
     subplot(2,2,4);mesh(X,Y,Z);view([0,1,1])
    