import pydicom as dcm
import numpy as np
import skimage 
from pydicom.multival import MultiValue


def rescaleto8bit(value,max_in,min_in,max_out,min_out, scala):
    """
    Function to rescale pixel data to 8 bits
    """
    if value<=max_in and value>=min_in:
        return (value- min_in)*scala
    elif value< min_in:
        return min_out
    else:
        return max_out

#with multiframe and not monochrome options
def get_preview_imagedata(ds: dcm.Dataset):
    number_frames = 1
    byte_per_pixel = 1 
    min = 0
    rescale_intercept =0
    rescale_slope = 1
    if [0x0028,0x0008] in ds:
        number_frames = int(ds[0x0028,0x0008].value)
    if [0x0028,0x0002] in ds:
        byte_per_pixel = int(ds[0x0028,0x0002].value )
    if byte_per_pixel<=2: #monochrome         
        if [0x0028, 0x1052] in ds:
            rescale_slope = float(ds.RescaleSlope)
            rescale_intercept = float(ds.RescaleIntercept)
        if rescale_slope !=1 and rescale_intercept != 0:
            data = ds.pixel_array* rescale_slope+rescale_intercept 
        else:
            data = ds.pixel_array
        min = np.min(data)
        max = np.max(data)
        wmin = min
        wmax = max
        if wmax == wmin:
            return None, None, None
        if [0x0028, 0x1050] in ds:
            window_center = ds[0x0028,0x1050].value
            window_width = ds[0x0028,0x1051].value
            if type(window_center) == MultiValue:
                window_center = window_center[0]
            if type(window_width) == MultiValue:
                window_width = window_width[0]
            wmin = (window_center-window_width/2)
            wmax = (window_center+window_width/2)
        
        scala = 255/(wmax-wmin)
        vect_rescale = np.vectorize(rescaleto8bit)
        data_rescaled = vect_rescale(data,wmax, wmin,255,0,scala).astype(np.uint8) 
    else: #rgb cpixel per byte >2  
        data_rescaled = skimage.color.rgb2gray(ds.pixel_array)
        data_rescaled = np.array([xi*255 for xi in data_rescaled]).astype(np.uint8) 
    new_pix_val = min
    if [0x0028,0x0004]in ds:
        lut = ds[0x0028,0x0004].value
        if lut.strip().lower()=='monochrome1':
            new_pix_val = max
    new_mask_value = int((new_pix_val - rescale_intercept)/rescale_slope)
    return data_rescaled, number_frames, new_mask_value


def mask_dicom_file(ds: dcm.Dataset, new_value, predictions, number_frames):

    byte_per_pixel = 1
    if [0x0028,0x0002] in ds:
        byte_per_pixel = int(ds[0x0028,0x0002].value )

    frame_list= ds.pixel_array[:] 
    
    if number_frames>1:
        for i in range(number_frames):
            
            for contour  in predictions.values():
                xs = contour[:,0]
                ys = contour[:,1]
                miny = np.min(ys)
                maxy = np.max(ys)
                minx = np.min(xs)
                maxx = np.max(xs)
                for y in range((int)(miny), (int)(maxy)):
                    for x in range((int)(minx), (int)(maxx)):
                        if byte_per_pixel <=2:
                            frame_list[i,y,x] = new_value
                        else:
                            frame_list[i,y,x] = [new_value,new_value,new_value]
    else:
        
        for contour  in predictions.values():
                #contour = group[1]
                xs = contour[:,0]
                ys = contour[:,1]
                miny = np.min(ys)
                maxy = np.max(ys)
                minx = np.min(xs)
                maxx = np.max(xs)
                for y in range((int)(miny), (int)(maxy)):
                    for x in range((int)(minx), (int)(maxx)):
                        if byte_per_pixel <=2:
                            frame_list[y,x] = new_value
                        else:
                            frame_list[y,x] = [new_value,new_value,new_value]   
        
    ds.PixelData =   frame_list.tobytes()     
   
    return ds  

def compute_gradient(image_gray)->np.ndarray:
    """
    Function to compute the gradients magnitude of the image
    """
    # Compute the gradients using the Sobel operator
    
    dx = skimage.filters.prewitt_h(image_gray)#sobel_h,   prewitt is better than sobel
    dy = skimage.filters.prewitt_v(image_gray)

    # Compute the magnitude and direction of the gradients
    mag = np.sqrt(dx**2 + dy**2)
    return (mag/mag.max()*255).astype(np.uint8)