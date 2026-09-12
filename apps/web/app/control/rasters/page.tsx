import {requireUser} from '../../../lib/session';
import {listLibrary} from '../../asset-actions';
import RasterLibrary from '../../../components/raster-library';
export default async function Rasters(){await requireUser();return <RasterLibrary initial={await listLibrary()}/>;}
