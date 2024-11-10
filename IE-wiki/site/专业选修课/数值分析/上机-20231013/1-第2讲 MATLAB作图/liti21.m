       [x,y,z]=peaks(30);
        cs=contour(x,y,z,8);
        clabel(cs) 
        xlabel('x-axis'),    ylabel('y-axis')
        title('contour  of peaks with labels')