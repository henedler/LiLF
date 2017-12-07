#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, glob, re
import numpy as np

parset_dir = "/home/fdg/scripts/LiLF/parsets/LOFAR_cal"
imaging    = True

# Temporary!
if 'tooth' in os.getcwd(): # tooth 2013
    datadir = '../cals-bkp/'
    bl2flag = 'CS031LBA'
elif 'bootes' in os.getcwd(): # bootes 2013
    datadir = '../cals-bkp/'
    bl2flag = 'CS013LBA\;CS031LBA'
elif 'survey' in os.getcwd():
    obs     = os.getcwd().split('/')[-2] # assumes .../c??-o??/3c196
    calname = os.getcwd().split('/')[-1] # assumes .../c??-o??/3c196
    datadir = '../../download/%s/%s' % (obs, calname)
    bl2flag = 'CS031LBA\;RS310LBA\;RS210LBA\;RS409LBA'
    if 'c07-o00' in os.getcwd() or 'c07-o01' in os.getcwd() or 'c07-o02' in os.getcwd() or 'c07-o03' in os.getcwd() or 'c07-o04' in os.getcwd() or 'c07-o05' in os.getcwd() or 'c07-o06' in os.getcwd():
        bl2flag = 'CS031LBA\;RS310LBA\;RS210LBA\;RS409LBA\;RS407LBA'
else:
    datadir = '../cals-bkp/'
    bl2flag = ''

########################################################
from LiLF import lib_ms, lib_util, lib_log, make_mask
lib_log.set_logger('pipeline-cal.logger')
logger = lib_log.logger
lib_util.check_rm('logs')
s = lib_util.Scheduler(dry = False)

# copy data
logger.info('Copy data...')
MSs = lib_ms.AllMSs([MS for MS in glob.glob(datadir+'/*MS') if not os.path.exists(os.path.basename(MS))], s)
MSs.run('DPPP ' + parset_dir + '/DPPP-avg.parset msin=$pathMS msout=$nameMS msin.datacolumn=DATA avg.timestep=1 avg.freqstep=1', \
                log='$nameMS_cp.log', commandType = "DPPP", maxThreads=20) # better than cp as can (de)activates dysco
MSs = lib_ms.AllMSs( glob.glob('*MS'), s )

## flag bad stations, flags will propagate
#logger.info("Flagging...")
#MSs.run("DPPP " + parset_dir + "/DPPP-flag.parset msin=$pathMS flag1.baseline=" + bl2flag, log="$nameMS_flag.log", commandType = "DPPP")
#
## predict to save time ms:MODEL_DATA
#logger.info('Predict...')
#calname = MSs.getListObj()[0].getNameField()
#skymodel   = "/home/fdg/scripts/LiLF/models/calib-simple.skydb"
#MSs.run("DPPP " + parset_dir + "/DPPP-predict.parset msin=$pathMS pre.sourcedb=" + skymodel + " pre.sources=" + calname, log = "$nameMS_pre.log", commandType = "DPPP")
#
###################################################
## 1: find the FR and remove it
#
## Beam correction DATA -> CORRECTED_DATA
#logger.info('Beam correction...')
#MSs.run("DPPP " + parset_dir + '/DPPP-beam.parset msin=$pathMS', log='$nameMS_beam.log', commandType = "DPPP")
#
## Convert to circular CORRECTED_DATA -> CORRECTED_DATA
#logger.info('Converting to circular...')
#MSs.run('mslin2circ.py -i $pathMS:CORRECTED_DATA -o $pathMS:CORRECTED_DATA', log='$nameMS_circ2lin.log', commandType ='python')
#
## Smooth data CORRECTED_DATA -> SMOOTHED_DATA (BL-based smoothing)
#logger.info('BL-smooth...')
#MSs.run('BLsmooth.py -r -i CORRECTED_DATA -o SMOOTHED_DATA $pathMS', log='$nameMS_smooth1.log', commandType ='python', maxThreads=20)
#
## Solve cal_SB.MS:SMOOTHED_DATA (only solve)
#logger.info('Calibrating...')
#for MS in MSs.getListStr():
#    lib_util.check_rm(MS+'/fr.h5')
#MSs.run('DPPP ' + parset_dir + '/DPPP-sol.parset msin=$pathMS sol.parmdb=$pathMS/fr.h5', log='$nameMS_sol1.log', commandType = "DPPP")

lib_util.run_losoto(s, 'fr', [ms+'/fr.h5' for ms in MSs.getListStr()], [parset_dir + '/losoto-fr.parset'])

#####################################################
# 2: find amplitude + align

# Beam correction DATA -> CORRECTED_DATA
logger.info('Beam correction...')
MSs.run('DPPP ' + parset_dir + '/DPPP-beam.parset msin=$pathMS', log='$nameMS_beam.log', commandType = "DPPP")

# Correct FR CORRECTED_DATA -> CORRECTED_DATA
logger.info('Faraday rotation correction...')
MSs.run('DPPP ' + parset_dir + '/DPPP-cor.parset msin=$pathMS cor.parmdb=cal-fr.h5 cor.correction=rotationmeasure000', log='$nameMS_corFR.log', commandType = "DPPP")

# Smooth data CORRECTED_DATA -> SMOOTHED_DATA (BL-based smoothing)
logger.info('BL-smooth...')
MSs.run('BLsmooth.py -r -i CORRECTED_DATA -o SMOOTHED_DATA $pathMS', log='$nameMS_smooth2.log', commandType ='python', maxThreads=20)

# Solve cal_SB.MS:SMOOTHED_DATA (only solve)
logger.info('Calibrating...')
for MS in MSs.getListStr():
    lib_util.check_rm(MS+'/amp.h5')
MSs.run('DPPP ' + parset_dir + '/DPPP-sol.parset msin=$pathMS sol.parmdb=$pathMS/amp.h5', log='$nameMS_sol2.log', commandType = "DPPP")

lib_util.run_losoto(s, 'amp', [ms+'/amp.h5' for ms in MSs.getListStr()], [parset_dir + '/losoto-flag.parset',parset_dir+'/losoto-amp.parset',parset_dir+'/losoto-align.parset'])

##################################################
# 3: find iono

# Correct cd+amp DATA -> CORRECTED_DATA
logger.info('Cross delay+ampBP correction...')
MSs.run('DPPP '+parset_dir+'/DPPP-cor.parset msin=$pathMS msin.datacolumn=DATA cor.steps=[polalign, amp] cor.parmdb=cal-amp.h5 \
        cor.polalign.correction=polalign cor.amp.correction=amplitudeSmooth000 cor.amp.updateweights=True', log='$nameMS_corAMP.log', commandType = "DPPP")

# Beam correction (and update weight in case of imaging) CORRECTED_DATA -> CORRECTED_DATA
logger.info('Beam correction...')
MSs.run('DPPP '+parset_dir+'/DPPP-beam.parset msin=$pathMS msin.datacolumn=CORRECTED_DATA corrbeam.updateweights=True', log='$nameMS_beam2.log', commandType = "DPPP")

# Correct FR CORRECTED_DATA -> CORRECTED_DATA
logger.info('Faraday rotation correction...')
MSs.run('DPPP '+parset_dir+'/DPPP-cor.parset msin=$pathMS cor.parmdb=cal-fr.h5 cor.correction=rotationmeasure000', log='$nameMS_corFR2.log', commandType = "DPPP")

# Smooth data CORRECTED_DATA -> SMOOTHED_DATA (BL-based smoothing)
logger.info('BL-smooth...')
MSs.run('BLsmooth.py -r -i CORRECTED_DATA -o SMOOTHED_DATA $pathMS', log='$nameMS_smooth3.log', commandType ='python', maxThreads=20)

# Solve cal_SB.MS:SMOOTHED_DATA (only solve)
logger.info('Calibrating...')
for MS in MSs.getListStr():
    lib_util.check_rm(ms+'/iono.h5')
MSs.run('DPPP '+parset_dir+'/DPPP-sol.parset msin=$pathMS sol.parmdb=$pathMS/iono.h5', log='$nameMS_sol3.log', commandType = "DPPP")

# if field model available, subtract it
field_model = '/home/fdg/scripts/LiLF/models/calfields/'+calname+'-field.skydb'
if os.path.exists(field_model):
    logger.info('Removing field sources...')

    logger.info('Ft+corrupt model...')
    MSs.run('DPPP '+parset_dir+'/DPPP-predict.parset msin=$pathMS pre.sourcedb='+field_model+' \
                pre.applycal.parmdb=$pathMS/iono.h5 pre.applycal.correction=phase000', log='$nameMS_field_pre.log', commandType = "DPPP")

    # Remove the field sources CORRECTED_DATA -> CORRECTED_DATA - MODEL_DATA
    logger.info('Subtract model...')
    MSs.run('taql "update $pathMS set CORRECTED_DATA = CORRECTED_DATA - MODEL_DATA"', log='$nameMS_field_taql.log', commandType ='general')

    # Smooth data CORRECTED_DATA -> SMOOTHED_DATA (BL-based smoothing)
    logger.info('BL-smooth...')
    MSs.run('BLsmooth.py -r -i CORRECTED_DATA -o SMOOTHED_DATA $pathMS', log='$nameMS_field_smooth.log', commandType ='python', maxThreads=20)

    # Solve cal_SB.MS:SMOOTHED_DATA (only solve)
    logger.info('Calibrating...')
    for MS in MSs.getListStr():
        lib_util.check_rm(ms+'/iono.h5')
    MSs.run('DPPP '+parset_dir+'/DPPP-sol.parset msin=$pathMS sol.parmdb=$pathMS/iono.h5', log='$nameMS_field_sol.log', commandType = "DPPP")

lib_util.run_losoto(s, 'iono', [ms+'/iono.h5' for ms in MSs.getListStr()], [parset_dir + '/losoto-iono.parset'])

if 'survey' in os.getcwd():
    logger.info('Copy survey caltable...')
    cal = 'cal_'+os.getcwd().split('/')[-2]
    logger.info('Copy: cal*h5 -> dsk:/disks/paradata/fdg/LBAsurvey/%s' % cal)
    os.system('ssh dsk "rm -rf /disks/paradata/fdg/LBAsurvey/%s"' % cal)
    os.system('ssh dsk "mkdir /disks/paradata/fdg/LBAsurvey/%s"' % cal)
    os.system('scp -q -r cal*h5 dsk:/disks/paradata/fdg/LBAsurvey/%s' % cal)

# a debug image
if imaging:
    logger.info("Imaging seciotn:")

    if not 'survey' in os.getcwd():
        MSs = lib_ms.AllMSs( glob.glob('./*MS')[int(len(glob.glob('./*MS'))/2.):], s ) # keep only upper band

    # Correct all CORRECTED_DATA (beam, CD, FR, BP corrected) -> CORRECTED_DATA
    logger.info('Amp/ph correction...')
    MSs.run("DPPP " + parset_dir + '/DPPP-cor.parset msin=$pathMS cor.parmdb=cal-iono.h5 cor.steps=[ph, amp] \
        cor.ph.correction=phase000 cor.amp.correction=amplitudeOrig000 cor.amp.updateweights=False', log='$nameMS_corG.log', commandType = "DPPP")

    logger.info('Subtract model...')
    MSs.run('taql "update $pathMS set CORRECTED_DATA = CORRECTED_DATA - MODEL_DATA"', log='$nameMS_taql2.log', commandType ='general')

    logger.info('Cleaning...')
    lib_util.check_rm('img')
    os.makedirs('img')
    imagename = 'img/wide'
    s.add('wsclean -reorder -name ' + imagename + ' -size 4000 4000 -mem 90 -j '+str(s.max_processors)+' -baseline-averaging 2.0 \
            -scale 5arcsec -weight briggs 0.0 -niter 100000 -no-update-model-required -mgain 0.9 \
            -pol I -joinchannels -fit-spectral-pol 2 -channelsout 10 -auto-threshold 20 '+MSs.getStrWsclean(), \
            log='wscleanA.log', commandType ='wsclean', processors='max')
    s.run(check = True)

    # make mask
    maskname = imagename+'-mask.fits'
    make_mask.make_mask(image_name = imagename+'-MFS-image.fits', mask_name = maskname, threshisl = 3, atrous_do=True)
    # remove CC not in mask
    for modelname in sorted(glob.glob(imagename+'*model.fits')):
        blank_image_fits(modelname, maskname, inverse=True)

    logger.info('Cleaning w/ mask')
    imagename = 'img/wideM'
    s.add('wsclean -reorder -name ' + imagename + ' -size 4000 4000 -mem 90 -j '+str(s.max_processors)+' -baseline-averaging 2.0 \
            -scale 5arcsec -weight briggs 0.0 -niter 100000 -no-update-model-required -mgain 0.8 -minuv-l 100 \
            -pol I -joinchannels -fit-spectral-pol 2 -channelsout 10 -auto-threshold 0.1 -save-source-list -apply-primary-beam -use-differential-lofar-beam \
            -fitsmask '+maskname+' '+MSs.getStrWsclean(), \
            log='wscleanB.log', commandType = 'wsclean', processors = 'max')
    s.run(check = True)

    # prepare mask
    logger.info('Masking skymodel...')
    make_mask.make_mask(image_name=imagename+'-MFS-image.fits', mask_name=imagename+'-mask.fits', threshisl=5, atrous_do=True)
    # apply mask
    logger.info('Predict (apply mask)...')
    lsm = lsmtool.load(imagename+'-sources-pb.txt')
    lsm.select('%s == True' % (imagename+'-mask.fits'))
    cRA, cDEC = get_phase_centre(MSs[0])
    lsm.select( lsm.getDistance(cRA, cDEC) > 0.1 )
    lsm.group('every')
    lsm.write(imagename+'-sources-pb-cut.txt', format='makesourcedb', clobber = True)
    del lsm

logger.info("Done.")
