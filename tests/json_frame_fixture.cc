#include "gemc_options.h"
#include <gemc/gstreamer/factories/JSON/gstreamerJSONFactory.h>
#include <stdexcept>

// Expose the existing protected frame hooks solely for this compatibility test.
class FrameJsonFixture : public GstreamerJsonFactory {
public:
    using GstreamerJsonFactory::GstreamerJsonFactory;
    using GStreamer::startStream;
    using GStreamer::publishFrameHeader;
    using GStreamer::publishPayload;
    using GStreamer::endStream;
};

int main(int argc, char* argv[]) {
    auto options = std::make_shared<GOptions>(argc, argv, gemc::defineOptions());
    auto logger = std::make_shared<GLogger>(options, "frame_test", GSTREAMER_LOGGER);
    GFrameDataCollection frame(new GFrameHeader(7, 10.0, logger), logger);
    frame.addIntegralPayload({1, 2, 3, 4, 5});
    auto streamer = std::make_shared<FrameJsonFixture>(options);
    streamer->define_gstreamer(gstreamer::getGStreamerDefinition(options).front());
    GStreamer& backend = *streamer;
    if (!backend.openConnection() || !streamer->startStream(&frame) ||
        !streamer->publishFrameHeader(frame.getHeader()) ||
        !streamer->publishPayload(frame.getIntegralPayload()) ||
        !streamer->endStream(&frame) || !streamer->closeConnection()) {
        throw std::runtime_error("JSON frame publication failed");
    }
}
